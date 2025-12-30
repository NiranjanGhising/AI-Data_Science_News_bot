#!/usr/bin/env python3
"""
Check tracked high-priority programs for openings/updates.
Run this more frequently (e.g., every 6-12 hours) for important programs.
Usage: python scripts/check_tracked_programs.py
"""
import os
import sys
from datetime import datetime

CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.deliver_telegram import send_message_telegram
from src.opportunity.program_tracker import load_tracked_programs, search_program_websites
from src.opportunity.http_client import PoliteHttpClient
from src.opportunity.logging_utils import log_event


def main():
    programs, alert_settings = load_tracked_programs()
    
    if not programs:
        print("No tracked programs found.")
        return
    
    high_priority = [p for p in programs if p.priority == "high"]
    print(f"Checking {len(high_priority)} high-priority programs...")
    
    http = PoliteHttpClient()
    
    findings = []
    for program in high_priority:
        print(f"  Checking: {program.name}...")
        
        for url in program.search_urls[:1]:
            try:
                response = http.get(url, timeout=15)
                if response.status_code != 200:
                    print(f"    ⚠️  Could not reach {url}")
                    continue
                
                content = response.text.lower()
                
                # Check for opening indicators
                opening_phrases = alert_settings.get("opening_indicators", [])
                found_phrases = [p for p in opening_phrases if p.lower() in content]
                
                if found_phrases:
                    findings.append({
                        "program": program,
                        "url": url,
                        "indicators": found_phrases[:3],
                    })
                    print(f"    🎯 FOUND: {', '.join(found_phrases[:3])}")
                else:
                    print(f"    ✓ No opening indicators found")
                    
            except Exception as e:
                print(f"    ❌ Error: {e}")
                log_event("program_check_error", program_id=program.id, error=str(e))
    
    if findings:
        print(f"\n{'='*50}")
        print(f"🚨 FOUND {len(findings)} POTENTIAL OPENINGS!")
        print(f"{'='*50}")
        
        # Send Telegram alert for findings
        lines = ["🚨 **Program Alert!**", ""]
        for f in findings:
            p = f["program"]
            lines.append(f"**{p.name}**")
            lines.append(f"Indicators: {', '.join(f['indicators'])}")
            lines.append(f"[Check Now]({f['url']})")
            if p.notes:
                lines.append(f"_{p.notes}_")
            lines.append("")
        
        try:
            send_message_telegram("\n".join(lines), parse_mode="Markdown")
            print("✅ Telegram alert sent!")
        except Exception as e:
            print(f"⚠️  Could not send Telegram: {e}")
            # Print the message anyway
            print("\nMessage that would have been sent:")
            print("\n".join(lines))
    else:
        print(f"\n✓ No program openings detected at this time.")


if __name__ == "__main__":
    main()
