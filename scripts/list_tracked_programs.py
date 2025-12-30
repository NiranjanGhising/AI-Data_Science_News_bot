#!/usr/bin/env python3
"""
List all tracked programs and their status.
Usage: python scripts/list_tracked_programs.py
"""
import os
import sys

# Fix Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.opportunity.program_tracker import load_tracked_programs, get_program_status_report


def main():
    programs, alert_settings = load_tracked_programs()
    
    if not programs:
        print("No tracked programs found.")
        print("Add programs to config/opportunity/tracked_programs.yaml")
        return
    
    print("=" * 60)
    print("TRACKED PROGRAMS")
    print("=" * 60)
    
    # Group by priority
    by_priority = {"high": [], "medium": [], "low": []}
    for p in programs:
        by_priority.get(p.priority, by_priority["medium"]).append(p)
    
    for priority, label in [("high", "🔴 HIGH PRIORITY"), ("medium", "🟡 MEDIUM PRIORITY"), ("low", "🟢 LOW PRIORITY")]:
        progs = by_priority[priority]
        if not progs:
            continue
        
        print(f"\n{label}")
        print("-" * 40)
        
        for p in progs:
            print(f"\n📌 {p.name}")
            print(f"   Category: {p.category}")
            if p.typical_timing:
                print(f"   Timing: {p.typical_timing}")
            if p.notes:
                print(f"   Notes: {p.notes}")
            if p.search_urls:
                print(f"   URL: {p.search_urls[0]}")
            print(f"   Keywords: {', '.join(p.keywords[:3])}...")
    
    print("\n" + "=" * 60)
    print(f"Total: {len(programs)} programs tracked")
    print(f"  High Priority: {len(by_priority['high'])}")
    print(f"  Medium Priority: {len(by_priority['medium'])}")
    print(f"  Low Priority: {len(by_priority['low'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
