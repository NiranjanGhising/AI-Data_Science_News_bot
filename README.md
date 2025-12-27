
# AI & Data Science Research Radar (Telegram-only)

Get **daily digests** and **priority alerts** in your Telegram group about the latest AI/Data Science updates:
- Focus on **top companies**: Google/DeepMind, OpenAI, Microsoft Research, Meta.
- Includes **new posts** from official blogs and **new papers** from arXiv, Semantic Scholar, Crossref, and Papers With Code.
- **Daily at 08:00 Nepal time (Asia/Kathmandu)** and **hourly priority alerts** (skip quiet hours).
- **Privacy-first**: No tokens or IDs in code—use GitHub Actions Secrets.

---

## ✨ Features
- **Telegram-only delivery**: short bullets + link + key findings.
- **Link summaries** (new): each AI item can include a 1–2 sentence summary from the link + a short “Why read” note.
- **High-signal sources**:
  - Company blogs: Google AI, DeepMind, OpenAI, Microsoft Research, Meta.
  - Research feeds: arXiv (cs.LG, cs.CL, stat.ML), Semantic Scholar, Crossref, Papers With Code.
- **Ranking & filtering**:
  - Major releases/announcements from top companies.
  - Practical dev items (SDKs, APIs, libraries, RAG, agents, workflows).
  - Papers with **code** and/or **SOTA** signals.

---

## 🚀 Quick Start (for anyone forking the repo)

### 1) Create a Telegram Bot & Group
1. In Telegram, talk to **@BotFather** → `/newbot` → follow prompts → copy your **bot token**.
2. Create a Telegram **group** (e.g., _Daily News on AI/Data Science_).
3. Add your bot to the group.

### 2) Get your `chat_id`
1. Send a message in your group (e.g., “hello”).
2. Open in your browser (replace `<YOUR_BOT_TOKEN>`):

https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates

3. Find `"chat": {"id": ...}` in the JSON.  
Example: `-1001234567789` (keep the minus sign).

---

### 3) Fork this repo & add GitHub Secrets
- Go to your fork → **Settings → Secrets and variables → Actions → New repository secret**:
- `TG_TOKEN` → your bot token.
- `TG_CHAT_ID` → your group chat id.

---

### 4) Enable GitHub Actions & run a test
- In your fork, open **Actions** → enable if prompted.
- Select **Daily Digest** workflow → **Run workflow** (manual test).
- You should see a message in your Telegram group.

---

## 🕒 Scheduling & Quiet Hours
- **Daily digest**: 08:00 NPT (Asia/Kathmandu) → `cron: "15 2 * * *"` (UTC).
- **Priority alerts**: hourly, skips quiet hours (22:00–07:00 NPT).

---

## 🔧 Customization
- Add/remove sources: `src/ingest_feeds.py`.
- Tune ranking keywords: `scripts/run_daily.py`.
- Change bullet count: `src/deliver_telegram.py`.
- Adjust quiet hours: `scripts/run_priority.py`.

### Link summaries (summary + “Why read”)
By default the daily digest / priority alerts will fetch each AI item’s URL and try to extract a short summary plus a short “Why read” signal.

Environment variables:
- `RR_SUMMARIZE_LINKS` (default `1`): set to `0` to disable fetching/summarizing links.
- `RR_USER_AGENT` (optional): override the HTTP User-Agent used to fetch pages.

Notes:
- Results are cached in `data/news_radar.db` (in the `ai_items` table) so the same link is not re-fetched every run.
- If Telegram formatting ever fails for a specific link/title, set `TG_DISABLE_MARKDOWN=1`.

---

## ❓ FAQ

**Q: Does this cost anything?**  
No—Telegram and GitHub Actions are free for public repos.

**Q: My bot isn’t posting.**  
- Check bot is in the group.
- Confirm `TG_CHAT_ID` via `getUpdates`.
- Trigger **Daily Digest** manually.

---

## 👐 Contributing
Pull requests welcome! Ideas:
- Add more sources (Hugging Face, NVIDIA, conference feeds).
- Improve ranking heuristics.
- Better summaries and figure handling.

---

## 📄 License
Released under the **MIT License** (see `LICENSE`).