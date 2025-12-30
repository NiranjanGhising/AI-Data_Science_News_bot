#!/usr/bin/env python3
"""
Health check for all opportunity sources.
Reports which sources are working and which are failing.

Usage: python scripts/health_check_sources.py
"""
import os
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

CURRENT_DIR = os.path.dirname(__file__)
REPO_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, os.pardir))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from src.opportunity.config_loader import load_sources
from src.opportunity import connectors_rss, connectors_atom
from src.opportunity.http_client import PoliteHttpClient


def check_source(source: dict, http: PoliteHttpClient) -> tuple[bool, int, str]:
    """Check if a source is working. Returns (success, item_count, error_message)."""
    url = source.get("url", "")
    parser = (source.get("parser") or "rss").lower()
    
    try:
        if parser == "rss":
            items = connectors_rss.fetch_rss(url, source)
        elif parser == "atom":
            items = connectors_atom.fetch_atom(url, source)
        else:
            # Skip non-RSS/Atom for now
            return True, -1, f"Skipped ({parser} parser)"
        
        return True, len(items), ""
    except Exception as e:
        return False, 0, str(e)[:50]


def main():
    sources = load_sources()
    http = PoliteHttpClient()
    
    print("=" * 70)
    print("OPPORTUNITY SOURCES HEALTH CHECK")
    print("=" * 70)
    
    working = []
    broken = []
    disabled = []
    
    for source in sources:
        name = source.get("name", "Unknown")
        enabled = source.get("enabled", False)
        
        if not enabled:
            disabled.append((name, "Disabled in config"))
            continue
        
        success, count, error = check_source(source, http)
        
        if success and count > 0:
            working.append((name, count))
        elif success and count == 0:
            broken.append((name, "Returns 0 items"))
        elif success and count == -1:
            disabled.append((name, error))
        else:
            broken.append((name, error))
    
    print("\n✅ WORKING SOURCES")
    print("-" * 50)
    for name, count in sorted(working, key=lambda x: -x[1]):
        print(f"  {name}: {count} items")
    
    print(f"\n❌ BROKEN SOURCES ({len(broken)})")
    print("-" * 50)
    for name, error in broken:
        print(f"  {name}: {error}")
    
    print(f"\n⏸️  DISABLED/SKIPPED ({len(disabled)})")
    print("-" * 50)
    for name, reason in disabled:
        print(f"  {name}: {reason}")
    
    print("\n" + "=" * 70)
    print(f"Summary: {len(working)} working, {len(broken)} broken, {len(disabled)} disabled")
    print("=" * 70)
    
    # Exit with error code if too many broken
    if len(broken) > len(working):
        print("\n⚠️  WARNING: More sources broken than working!")
        sys.exit(1)


if __name__ == "__main__":
    main()
