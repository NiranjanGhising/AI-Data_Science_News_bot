"""
Program Tracker - Actively monitors specific programs you don't want to miss.
This supplements RSS feeds with active web searching for tracked programs.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

import yaml

from .http_client import PoliteHttpClient
from .logging_utils import log_event
from .normalize import OpportunityItem

CONFIG_PATH = os.path.join(
    os.path.dirname(__file__), "..", "..", "config", "opportunity", "tracked_programs.yaml"
)


@dataclass
class TrackedProgram:
    id: str
    name: str
    keywords: list[str] = field(default_factory=list)
    search_urls: list[str] = field(default_factory=list)
    typical_timing: str = ""
    category: str = "program"
    priority: str = "medium"
    notes: str = ""


def load_tracked_programs() -> tuple[list[TrackedProgram], dict[str, Any]]:
    """Load tracked programs from config."""
    if not os.path.exists(CONFIG_PATH):
        return [], {}
    
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    
    programs = []
    for p in data.get("tracked_programs", []):
        programs.append(TrackedProgram(
            id=p.get("id", ""),
            name=p.get("name", ""),
            keywords=p.get("keywords", []),
            search_urls=p.get("search_urls", []),
            typical_timing=p.get("typical_timing", ""),
            category=p.get("category", "program"),
            priority=p.get("priority", "medium"),
            notes=p.get("notes", ""),
        ))
    
    alert_settings = data.get("alert_settings", {})
    return programs, alert_settings


def check_content_for_programs(
    content: str,
    programs: list[TrackedProgram],
    alert_settings: dict[str, Any],
) -> list[dict[str, Any]]:
    """Check if content mentions any tracked programs and if they're opening."""
    matches = []
    content_lower = content.lower()
    
    opening_indicators = [
        s.lower() for s in alert_settings.get("opening_indicators", [])
    ]
    
    for program in programs:
        for keyword in program.keywords:
            if keyword.lower() in content_lower:
                # Check if it indicates opening/availability
                is_opening = any(ind in content_lower for ind in opening_indicators)
                
                matches.append({
                    "program": program,
                    "keyword_matched": keyword,
                    "is_opening": is_opening,
                    "priority": program.priority,
                })
                break  # Don't double-count same program
    
    return matches


def enrich_item_with_program_match(
    item: OpportunityItem,
    programs: list[TrackedProgram],
    alert_settings: dict[str, Any],
) -> OpportunityItem:
    """Enrich an opportunity item if it matches a tracked program."""
    text = f"{item.title} {item.summary}".lower()
    
    matches = check_content_for_programs(text, programs, alert_settings)
    
    if not matches:
        return item
    
    # Take the highest priority match
    priority_order = {"high": 3, "medium": 2, "low": 1}
    matches.sort(key=lambda m: priority_order.get(m["priority"], 0), reverse=True)
    best_match = matches[0]
    program = best_match["program"]
    
    # Boost score for tracked programs
    score_boost = 0.3 if program.priority == "high" else 0.15
    new_score = min(1.0, item.score + score_boost)
    
    # Mark as urgent if it's opening
    urgent = item.urgent or best_match["is_opening"]
    
    # Add program notes to summary
    enhanced_summary = item.summary
    if program.notes and program.notes not in (item.summary or ""):
        enhanced_summary = f"{item.summary}\n\n📌 {program.notes}" if item.summary else program.notes
    
    log_event(
        "program_match",
        program_id=program.id,
        item_title=item.title,
        is_opening=best_match["is_opening"],
    )
    
    return OpportunityItem(
        **{
            **item.__dict__,
            "score": new_score,
            "urgent": urgent,
            "category": program.category,
            "summary": enhanced_summary,
            "tracked_program_id": program.id,
            "tracked_program_name": program.name,
        }
    )


def get_program_status_report(programs: list[TrackedProgram]) -> str:
    """Generate a status report of all tracked programs."""
    lines = ["📋 **Tracked Programs Status**", ""]
    
    by_priority = {"high": [], "medium": [], "low": []}
    for p in programs:
        by_priority.get(p.priority, by_priority["medium"]).append(p)
    
    for priority, progs in [("high", by_priority["high"]), ("medium", by_priority["medium"]), ("low", by_priority["low"])]:
        if not progs:
            continue
        emoji = "🔴" if priority == "high" else "🟡" if priority == "medium" else "🟢"
        lines.append(f"{emoji} **{priority.upper()} PRIORITY**")
        for p in progs:
            lines.append(f"  • {p.name}")
            if p.typical_timing:
                lines.append(f"    _Timing: {p.typical_timing}_")
        lines.append("")
    
    return "\n".join(lines)


async def search_program_websites(
    programs: list[TrackedProgram],
    http: Optional[PoliteHttpClient] = None,
) -> list[dict[str, Any]]:
    """
    Actively check program websites for updates.
    Returns list of findings with potential opportunities.
    """
    if http is None:
        http = PoliteHttpClient()
    
    findings = []
    
    for program in programs:
        if program.priority != "high":
            continue  # Only actively search high-priority programs
        
        for url in program.search_urls[:1]:  # Just check main URL
            try:
                response = http.get(url, timeout=10)
                if response.status_code != 200:
                    continue
                
                content = response.text.lower()
                
                # Look for opening indicators
                opening_phrases = [
                    "applications open",
                    "register now",
                    "sign up",
                    "enrollment open",
                    "join now",
                    "apply now",
                ]
                
                found_opening = any(phrase in content for phrase in opening_phrases)
                
                if found_opening:
                    findings.append({
                        "program": program,
                        "url": url,
                        "type": "opening_detected",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    })
                    log_event(
                        "program_opening_detected",
                        program_id=program.id,
                        url=url,
                    )
            except Exception as e:
                log_event(
                    "program_search_error",
                    program_id=program.id,
                    url=url,
                    error=str(e),
                )
    
    return findings
