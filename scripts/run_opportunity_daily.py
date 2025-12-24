import os
import sys
from datetime import datetime

# Ensure repository root is on sys.path so `src` package is importable
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.deliver_telegram import send_message_telegram, format_opportunity_bullet
from src.opportunity.pipeline import run_opportunity_pipeline, select_daily_items
from src.opportunity.config_loader import load_scoring
from src.opportunity.storage import OpportunityStore


def main():
    db_path = os.path.join(REPO_ROOT, "data", "opportunity_radar.db")
    store = OpportunityStore(db_path)

    scoring_cfg = load_scoring()
    items = run_opportunity_pipeline(store=store)
    daily = select_daily_items(items, scoring_cfg)

    if not daily:
        return

    date_label = datetime.now().strftime("%Y-%m-%d")
    lines = [f"🎓 Opportunities — {date_label}", ""]
    for it in daily:
        lines.append(format_opportunity_bullet(it.__dict__))

    send_message_telegram("\n".join(lines), parse_mode="Markdown")
    store.mark_notified([i.canonical_url for i in daily if i.canonical_url])


if __name__ == "__main__":
    main()
