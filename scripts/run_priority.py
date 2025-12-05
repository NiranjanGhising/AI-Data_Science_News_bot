import os
import sys
import datetime

# Ensure repository root is on sys.path so `src` package is importable
CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
from src.ingest_feeds import pull_company_posts
from src.deliver_telegram import send_digest_telegram

def is_quiet_hours_utc():
    # Quiet hours in NPT (22:00-07:00). Approx skip in UTC:
    # NPT = UTC+05:45 → quiet hours ≈ 16:15–01:15 UTC.
    # We’ll skip hours 16..23 and 0..1 for safety.
    utc_hour = datetime.datetime.utcnow().hour
    return utc_hour in list(range(16, 24)) + [0, 1]

def main():
    if is_quiet_hours_utc():
        print("Quiet hours; skipping alerts.")
        return

    posts = pull_company_posts()
    big = [p for p in posts if any(k in p["title"].lower()
            for k in ["introducing","announcing","release","model","api",
                      "sdk","agent","workflow","preview","launch","update"])]
    if big:
        # send up to 3 items in one alert
        for i in big[:3]:
            i["key_findings"] = "- Major release/preview\n- Likely high visibility\n- See link for details"
        send_digest_telegram(big[:3], bullets=3)

if __name__ == "__main__":
    main()
