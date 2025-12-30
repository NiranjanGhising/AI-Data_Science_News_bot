#!/usr/bin/env python3
"""
Manually add an opportunity to the database.
Usage: python scripts/add_opportunity.py "Title" "URL" --category challenge --urgent
"""
import argparse
import os
import sys
from datetime import datetime, timezone

CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.opportunity.normalize import OpportunityItem
from src.opportunity.storage import OpportunityStore


def main():
    parser = argparse.ArgumentParser(description="Manually add an opportunity")
    parser.add_argument("title", help="Title of the opportunity")
    parser.add_argument("url", help="URL of the opportunity")
    parser.add_argument("--summary", "-s", default="", help="Summary/description")
    parser.add_argument(
        "--category", "-c",
        default="program",
        choices=["program", "internship", "course", "certification", "challenge", "scholarship", "conference"],
        help="Category of opportunity"
    )
    parser.add_argument("--urgent", "-u", action="store_true", help="Mark as urgent")
    parser.add_argument("--limited", "-l", action="store_true", help="Mark as limited time")
    parser.add_argument("--deadline", "-d", help="Deadline date (YYYY-MM-DD)")
    parser.add_argument("--score", type=float, default=0.8, help="Score (0-1, default 0.8)")
    
    args = parser.parse_args()
    
    deadline_at = None
    if args.deadline:
        try:
            deadline_at = datetime.strptime(args.deadline, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            print(f"Invalid deadline format: {args.deadline}. Use YYYY-MM-DD")
            sys.exit(1)
    
    item = OpportunityItem(
        title=args.title,
        summary=args.summary,
        content_url=args.url,
        canonical_url=args.url,
        published_at=datetime.now(timezone.utc),
        deadline_at=deadline_at,
        source="manual",
        source_id="manual",
        tags=["manual"],
        category=args.category,
        urgent=args.urgent,
        limited_time=args.limited,
        score=args.score,
    )
    
    db_path = os.path.join(REPO_ROOT, "data", "opportunity_radar.db")
    store = OpportunityStore(db_path)
    store.init()
    store.upsert_items([item])
    
    print(f"✅ Added opportunity: {args.title}")
    print(f"   URL: {args.url}")
    print(f"   Category: {args.category}")
    print(f"   Urgent: {args.urgent}")
    if deadline_at:
        print(f"   Deadline: {deadline_at.strftime('%Y-%m-%d')}")


if __name__ == "__main__":
    main()
