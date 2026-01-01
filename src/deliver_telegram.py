import os
import requests

# Telegram message character limit
TELEGRAM_MAX_LENGTH = 4096


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

    # Split long messages to avoid Telegram's 4096 char limit
    chunks = _split_message(text, TELEGRAM_MAX_LENGTH)
    
    for chunk in chunks:
        payload = {"chat_id": chat_id, "text": chunk}
        if parse_mode:
            payload["parse_mode"] = parse_mode

        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=payload,
            timeout=30,
        )
        if not resp.ok:
            body = (resp.text or "").strip()
            if len(body) > 1200:
                body = body[:1200] + "..."
            raise RuntimeError(f"Telegram sendMessage failed: HTTP {resp.status_code}: {body}")


def _split_message(text: str, max_length: int) -> list[str]:
    """Split a message into chunks that fit within Telegram's character limit.
    
    Tries to split at paragraph boundaries (double newlines), then single newlines,
    to keep related content together.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    remaining = text
    
    while remaining:
        if len(remaining) <= max_length:
            chunks.append(remaining)
            break
        
        # Find the best split point within the limit
        split_at = max_length
        
        # Try to split at a double newline (paragraph break)
        para_break = remaining.rfind("\n\n", 0, max_length)
        if para_break > max_length // 2:  # Only use if it's not too early
            split_at = para_break + 2  # Include the newlines in this chunk
        else:
            # Try to split at a single newline
            line_break = remaining.rfind("\n", 0, max_length)
            if line_break > max_length // 2:
                split_at = line_break + 1
            else:
                # Last resort: split at a space
                space = remaining.rfind(" ", 0, max_length)
                if space > max_length // 2:
                    split_at = space + 1
                # If no good split point, just hard cut at max_length
        
        chunks.append(remaining[:split_at].rstrip())
        remaining = remaining[split_at:].lstrip()
    
    return chunks

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
    tracked_program = item.get("tracked_program_name")

    markers = []
    if item.get("urgent"):
        markers.append("🔥")
    if item.get("limited_time"):
        markers.append("⏳")
    if tracked_program:
        markers.append("📌")  # Tracked program indicator

    prefix = " ".join(markers) + " " if markers else "⚡ "
    parts = [f"{prefix}{title}", f"{category}"]
    if tracked_program:
        parts.append(f"\\[{_escape_md(tracked_program)}\\]")
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
