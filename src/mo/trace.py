"""Dev trace: group traced calls into runs and flag what didn't happen (see docs/DESIGN.md).

A run starts at each kit (mo_write or mo_read). Every mo_check after it is one version of the
draft: the first is what ChatGPT generated, the later ones are its revisions after MO's flags.
MO never rewrites text, so the versions show exactly what MO's flags changed.
"""

from __future__ import annotations

from typing import Any

KITS = ("mo_write", "mo_read")
DRIFT = 0.05  # voice distance rising this much from the first version counts as drift


def runs(calls: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: list[dict[str, Any]] = []
    current = None
    for call in calls:
        if call["tool"] in KITS or current is None:
            current = {"at": call["at"], "kit": None, "versions": [], "events": []}
            grouped.append(current)
        if call["tool"] in KITS and not call["error"]:
            current["kit"] = call
        elif call["tool"] == "mo_check" and not call["error"]:
            result = call["result"]
            current["versions"].append({"at": call["at"], "draft": call["args"].get("draft", ""),
                                        "status": result["status"], "flags": result["flags"],
                                        "metrics": result["metrics"]})
        else:
            current["events"].append(call)
    for run in grouped:
        run["warnings"] = warnings(run)
    return grouped


def warnings(run: dict[str, Any]) -> list[str]:
    found = []
    kit, versions = run["kit"], run["versions"]
    if kit is None and versions:
        found.append("Draft checked without a kit: ChatGPT never fetched your rules or samples for it.")
    if kit:
        result = kit["result"]
        if not result["rules"] and not result.get("exemplars"):
            found.append("Empty kit: no rules and no samples, so ChatGPT had nothing of yours to follow.")
        if not versions:
            found.append("Kit fetched but no draft was checked: whatever ChatGPT showed you was never checked.")
    if versions:
        empty = not (kit and (kit["result"]["rules"] or kit["result"].get("exemplars")))
        if empty and versions[-1]["status"] == "passed":
            found.append("Checks passed with nothing to compare against: a pass here means no AI tells or "
                         "invented numbers, not that it sounds like you.")
        if versions[-1]["status"] != "passed":
            found.append(f"Last checked version still had {len(versions[-1]['flags'])} flag(s).")
        distances = [v["metrics"].get("voice_distance") for v in versions]
        if len(distances) > 1 and None not in (distances[0], distances[-1]) and distances[-1] - distances[0] > DRIFT:
            found.append(f"Voice drift: distance from your samples rose from {distances[0]} to {distances[-1]}.")
    return found
