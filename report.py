"""
report.py — Writes report.json and report.log for Defaultclone.
Token MUST NOT appear in any output file.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

from cloner import CloneResult
from ui import info


# ── Public API ────────────────────────────────────────────────────────────────

def write_reports(
    output_dir: Path,
    target: str,
    account_type: str,
    results: list[CloneResult],
    elapsed: float,
) -> None:
    """Write report.json and report.log to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    cloned  = [r for r in results if r.status == "cloned"]
    skipped = [r for r in results if r.status == "skipped"]
    failed  = [r for r in results if r.status == "failed"]

    timestamp = datetime.now(tz=timezone.utc).isoformat()

    # ── JSON report ───────────────────────────────────────────────────────────
    report_data = {
        "meta": {
            "tool":        "defaultclone",
            "timestamp":   timestamp,
            "target":      target,
            "account_type": account_type,
            "elapsed_seconds": round(elapsed, 2),
        },
        "summary": {
            "total":   len(results),
            "cloned":  len(cloned),
            "skipped": len(skipped),
            "failed":  len(failed),
        },
        "repos": {
            "cloned":  [{"name": r.name, "url": r.url, "elapsed": round(r.elapsed, 2)} for r in cloned],
            "skipped": [{"name": r.name, "url": r.url, "reason": r.reason}             for r in skipped],
            "failed":  [{"name": r.name, "url": r.url, "reason": r.reason}             for r in failed],
        },
    }

    json_path = output_dir / "report.json"
    with json_path.open("w") as f:
        json.dump(report_data, f, indent=2)

    # ── Plain-text log ────────────────────────────────────────────────────────
    log_path = output_dir / "report.log"
    mins, secs = divmod(int(elapsed), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    lines = [
        f"DEFAULTCLONE REPORT",
        f"Generated : {timestamp}",
        f"Target    : {target} ({account_type})",
        f"Elapsed   : {elapsed_str}",
        f"Output    : {output_dir}",
        "",
        f"SUMMARY",
        f"  Total   : {len(results)}",
        f"  Cloned  : {len(cloned)}",
        f"  Skipped : {len(skipped)}",
        f"  Failed  : {len(failed)}",
        "",
    ]

    if cloned:
        lines.append("CLONED")
        for r in cloned:
            lines.append(f"  [OK]  {r.name}  ({r.elapsed:.1f}s)")
        lines.append("")

    if skipped:
        lines.append("SKIPPED")
        for r in skipped:
            lines.append(f"  [SK]  {r.name}  ({r.reason})")
        lines.append("")

    if failed:
        lines.append("FAILED")
        for r in failed:
            lines.append(f"  [ER]  {r.name}  — {r.reason}")
        lines.append("")

    with log_path.open("w") as f:
        f.write("\n".join(lines))

    info(f"Reports written: [dim]{json_path}[/dim]  [dim]{log_path}[/dim]")
