import os
import requests


TELEGRAM_MAX_MESSAGE_LEN = int(os.getenv("TG_MAX_MESSAGE_LEN", "4000"))
TELEGRAM_MAX_MESSAGE_BYTES = int(os.getenv("TG_MAX_MESSAGE_BYTES", "4000"))


def _tg_utf16_units(text: str) -> int:
    # Telegram counts characters in UTF-16 code units.
    return len((text or "").encode("utf-16-le")) // 2


def _tg_utf8_bytes(text: str) -> int:
    return len((text or "").encode("utf-8"))


def _fits_telegram_limits(text: str, *, max_units: int, max_bytes: int) -> bool:
    return _tg_utf16_units(text) <= max_units and _tg_utf8_bytes(text) <= max_bytes


def _hard_split(text: str, *, max_units: int, max_bytes: int) -> list[str]:
    # Split by characters, ensuring each chunk fits both constraints.
    out: list[str] = []
    buf = ""
    for ch in text:
        cand = buf + ch
        if buf and not _fits_telegram_limits(cand, max_units=max_units, max_bytes=max_bytes):
            out.append(buf)
            buf = ch
        else:
            buf = cand
    if buf:
        out.append(buf)
    return out


def _split_telegram_text(text: str) -> list[str]:
    text = "" if text is None else str(text)
    if _fits_telegram_limits(text, max_units=TELEGRAM_MAX_MESSAGE_LEN, max_bytes=TELEGRAM_MAX_MESSAGE_BYTES):
        return [text]

    # Prefer splitting on line boundaries.
    lines = text.split("\n")
    chunks: list[str] = []
    buf = ""

    def flush() -> None:
        nonlocal buf
        if buf:
            chunks.append(buf)
            buf = ""

    for line in lines:
        candidate = line if not buf else (buf + "\n" + line)
        if _fits_telegram_limits(candidate, max_units=TELEGRAM_MAX_MESSAGE_LEN, max_bytes=TELEGRAM_MAX_MESSAGE_BYTES):
            buf = candidate
            continue

        flush()

        # If the single line is too long, hard-split it.
        if not _fits_telegram_limits(line, max_units=TELEGRAM_MAX_MESSAGE_LEN, max_bytes=TELEGRAM_MAX_MESSAGE_BYTES):
            chunks.extend(_hard_split(line, max_units=TELEGRAM_MAX_MESSAGE_LEN, max_bytes=TELEGRAM_MAX_MESSAGE_BYTES))
        else:
            buf = line

    flush()
    return [c for c in chunks if c.strip()]


def _escape_md(text: str) -> str:
    # Telegram Markdown (legacy) is finicky; do a small, safe subset.
    # We avoid fancy formatting and mainly escape '*' and '_' which are common.
    if text is None:
        return ""
    return (
        str(text)
        .replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("[", "\\[")
        .replace("]", "\\]")
        .strip()
    )


def send_message_telegram(text: str, *, parse_mode: str = "Markdown") -> None:
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")
    if not token or not chat_id:
        raise RuntimeError("Missing TG_TOKEN or TG_CHAT_ID")

    # Allow disabling Markdown entirely if Telegram rejects formatting.
    # Useful for debugging and for edge-case titles/URLs that break Markdown.
    if os.getenv("TG_DISABLE_MARKDOWN") == "1":
        parse_mode = ""

    # Telegram hard limit is ~4096 "characters" (UTF-16 units). We use a safety margin.
    parts = _split_telegram_text(text)

    last_error: RuntimeError | None = None
    for part in parts:
        payload = {"chat_id": chat_id, "text": part}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            timeout=30,
        )

        # Telegram Markdown can fail on edge-case titles/URLs. Auto-fallback to plain text.
        if (not resp.ok) and parse_mode:
            body0 = (resp.text or "").lower()
            if resp.status_code == 400 and ("can't parse" in body0 or "cant parse" in body0 or "parse entities" in body0):
                payload2 = {"chat_id": chat_id, "text": part}
                resp2 = requests.post(
                    f"https://api.telegram.org/bot{token}/sendMessage",
                    data=payload2,
                    timeout=30,
                )
                resp = resp2

        if not resp.ok:
            body = (resp.text or "").strip()
            if len(body) > 1200:
                body = body[:1200] + "..."
            last_error = RuntimeError(f"Telegram sendMessage failed: HTTP {resp.status_code}: {body}")
            break

    if last_error is not None:
        raise last_error

def send_digest_telegram(items, bullets=6):
    top = items[:bullets]
    text = "\n\n".join([
        f"• *{_escape_md(i['title'])}*\n_{_escape_md(i.get('source',''))} — {_escape_md(i.get('date',''))}_\n"
        f"{ _escape_md(i.get('key_findings','(see link)')) }\n{ _escape_md(i['url']) }"
        for i in top
    ])

    send_message_telegram(text, parse_mode="Markdown")


def _format_opportunity_deadline(deadline_at) -> str:
    if not deadline_at:
        return ""
    try:
        # Deadline is stored UTC; show as YYYY-MM-DD for simplicity.
        return deadline_at.date().isoformat()
    except Exception:
        return ""


def format_opportunity_bullet(item) -> str:
    # Expected keys: title, category, deadline_at, source, content_url, urgent, limited_time
    title = _escape_md(item.get("title", ""))
    category = _escape_md(item.get("category", "program"))
    source = _escape_md(item.get("source", ""))
    url = _escape_md(item.get("content_url") or item.get("url") or "")
    deadline = _escape_md(_format_opportunity_deadline(item.get("deadline_at")))

    ascii_only = os.getenv("RR_ASCII_ONLY") == "1"

    markers = []
    if item.get("urgent"):
        markers.append("URGENT" if ascii_only else "🔥")
    if item.get("limited_time"):
        markers.append("LIMITED" if ascii_only else "⏳")

    if markers:
        prefix = (" ".join(markers) + " ")
    else:
        prefix = ("* " if ascii_only else "⚡ ")
    parts = [f"{prefix}{title}", f"{category}"]
    if deadline:
        parts.append(f"deadline {deadline}")
    if source:
        parts.append(source)
    line = " — ".join(parts)
    return f"• {line}\n{url}".strip()


def send_combined_daily_digest(*, date_label: str, ai_items: list[dict], opp_items: list[dict]) -> None:
    text = build_combined_daily_text(date_label=date_label, ai_items=ai_items, opp_items=opp_items)
    send_message_telegram(text, parse_mode="Markdown")


def build_combined_daily_text(*, date_label: str, ai_items: list[dict], opp_items: list[dict]) -> str:
    lines = [f"Daily Digest — {_escape_md(date_label)}", "", "🧠 AI / Research"]
    if ai_items:
        for it in ai_items:
            title = _escape_md(it.get("title", ""))
            url = _escape_md(it.get("url", ""))
            summary = _escape_md(it.get("summary", ""))
            why_read = _escape_md(it.get("why_read", ""))

            block = [f"• {title}"]
            if summary:
                block.append(f"Summary: {summary}")
            if why_read:
                block.append(f"Why read: {why_read}")
            if url:
                block.append(url)
            lines.append("\n".join(block))
    else:
        lines.append("• (no new items)")

    lines += ["", "🎓 Opportunities"]
    if opp_items:
        for it in opp_items:
            lines.append(format_opportunity_bullet(it))
            if it.get("prep_checklist"):
                chk = ", ".join(str(x) for x in list(it.get("prep_checklist"))[:3])
                lines.append(f"  Prep: {_escape_md(chk)}")
    else:
        lines.append("• (no new items)")
    return "\n".join(lines)


def send_combined_priority_alert(*, ai_items: list[dict], opp_items: list[dict]) -> None:
    text = build_combined_priority_text(ai_items=ai_items, opp_items=opp_items)
    if not text.strip():
        return
    send_message_telegram(text, parse_mode="Markdown")


def build_combined_priority_text(*, ai_items: list[dict], opp_items: list[dict]) -> str:
    lines = ["🚨 Priority Alerts", ""]
    if ai_items:
        lines.append("🧠 AI / Research")
        for it in ai_items:
            title = _escape_md(it.get("title", ""))
            url = _escape_md(it.get("url", ""))
            summary = _escape_md(it.get("summary", ""))
            why_read = _escape_md(it.get("why_read", ""))

            block = [f"• {title}"]
            if summary:
                block.append(f"Summary: {summary}")
            if why_read:
                block.append(f"Why read: {why_read}")
            if url:
                block.append(url)
            lines.append("\n".join(block))
        lines.append("")

    if opp_items:
        lines.append("🎓 Opportunities (urgent)")
        for it in opp_items:
            lines.append(format_opportunity_bullet(it))

    # If nothing beyond header.
    return "\n".join(lines).strip() if (ai_items or opp_items) else ""

def send_photo_telegram(caption, photo_url):
    token = os.getenv("TG_TOKEN")
    chat_id = os.getenv("TG_CHAT_ID")

    if not token or not chat_id:
        raise RuntimeError("Missing TG_TOKEN or TG_CHAT_ID")

    parse_mode = "Markdown"
    if os.getenv("TG_DISABLE_MARKDOWN") == "1":
        parse_mode = ""

    payload = {"chat_id": chat_id, "caption": caption, "photo": photo_url}
    if parse_mode:
        payload["parse_mode"] = parse_mode

    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendPhoto",
        data=payload,
        timeout=30,
    )
    if not resp.ok:
        body = (resp.text or "").strip()
        if len(body) > 1200:
            body = body[:1200] + "..."
        raise RuntimeError(f"Telegram sendPhoto failed: HTTP {resp.status_code}: {body}")
