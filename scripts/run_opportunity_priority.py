import os
import sys
import datetime

# Ensure repository root is on sys.path so `src` package is importable
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.deliver_telegram import send_message_telegram, format_opportunity_bullet
from src.opportunity.config_loader import load_scoring
from src.opportunity.pipeline import run_opportunity_pipeline, select_priority_items
from src.opportunity.storage import OpportunityStore


def is_quiet_hours_utc():
    # Quiet hours in NPT (22:00-07:00). Approx skip in UTC:
    # NPT = UTC+05:45 → quiet hours ≈ 16:15–01:15 UTC.
    # We’ll skip hours 16..23 and 0..1 for safety.
    utc_hour = datetime.datetime.now(datetime.UTC).hour
    return utc_hour in list(range(16, 24)) + [0, 1]


def main():
    if os.getenv("FORCE_RUN") == "1":
        pass
    elif is_quiet_hours_utc():
        print("Quiet hours; skipping alerts.")
        return

    db_path = os.path.join(REPO_ROOT, "data", "opportunity_radar.db")
    store = OpportunityStore(db_path)

    scoring_cfg = load_scoring()

    # Pipeline returns unnotified items if store is provided.
    items = run_opportunity_pipeline(store=store)
    urgent = select_priority_items(items, scoring_cfg)

    if not urgent:
        return

    lines = ["🚨 Opportunity Alerts (urgent)", ""]
    for it in urgent:
        lines.append(format_opportunity_bullet(it.__dict__))

    send_message_telegram("\n".join(lines), parse_mode="Markdown")
    store.mark_notified([i.canonical_url for i in urgent if i.canonical_url])


if __name__ == "__main__":
    main()
