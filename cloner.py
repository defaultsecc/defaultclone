"""
cloner.py — Threaded git clone logic for Defaultclone.
"""

from __future__ import annotations

import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskID,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)

from ui import THEME, console

# ── Result dataclass ──────────────────────────────────────────────────────────

@dataclass
class CloneResult:
    name:    str
    url:     str
    status:  str          # "cloned" | "skipped" | "failed"
    reason:  str = ""
    elapsed: float = 0.0


# ── Progress bar factory ──────────────────────────────────────────────────────

def _make_progress() -> Progress:
    return Progress(
        SpinnerColumn(spinner_name="dots", style="red"),
        TextColumn("[red][[/red][bold white]{task.description}[/bold white][red]][/red]"),
        BarColumn(bar_width=None, style="bar.back", complete_style="bar.fill", finished_style="green"),
        MofNCompleteColumn(),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        TextColumn("[dim]{task.fields[status_line]}[/dim]"),
        console=console,
        transient=False,
    )


# ── Core clone function ───────────────────────────────────────────────────────

def _clone_one(
    repo: dict,
    output_dir: Path,
    depth: Optional[int],
    retries: int,
    token: Optional[str],
) -> CloneResult:
    name     = repo["name"]
    clone_url = repo["clone_url"]
    dest     = output_dir / name

    # Inject token into HTTPS URL if available
    if token and clone_url.startswith("https://github.com/"):
        clone_url = clone_url.replace(
            "https://github.com/",
            f"https://{token}@github.com/",
            1,
        )

    # Already cloned?
    if dest.exists() and (dest / ".git").exists():
        return CloneResult(name=name, url=repo["clone_url"], status="skipped", reason="already exists")

    cmd = ["git", "clone", "--quiet"]
    if depth:
        cmd += ["--depth", str(depth)]
    cmd += [clone_url, str(dest)]

    start = time.monotonic()
    last_error = ""

    for attempt in range(1 + retries):
        try:
            result = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=300,
            )
            elapsed = time.monotonic() - start
            if result.returncode == 0:
                return CloneResult(name=name, url=repo["clone_url"], status="cloned", elapsed=elapsed)
            last_error = result.stderr.decode(errors="replace").strip().splitlines()[-1] if result.stderr else "unknown error"
        except subprocess.TimeoutExpired:
            last_error = "clone timed out after 300s"
        except FileNotFoundError:
            return CloneResult(
                name=name, url=repo["clone_url"],
                status="failed", reason="git not found in PATH",
            )
        except Exception as exc:
            last_error = str(exc)

        if attempt < retries:
            time.sleep(2 ** attempt)  # brief back-off before retry

    elapsed = time.monotonic() - start
    return CloneResult(
        name=name, url=repo["clone_url"],
        status="failed", reason=last_error, elapsed=elapsed,
    )


# ── Batch cloner ──────────────────────────────────────────────────────────────

def clone_all(
    repos: list[dict],
    output_dir: Path,
    depth: Optional[int],
    concurrency: int,
    retries: int,
    token: Optional[str],
    dry_run: bool = False,
) -> list[CloneResult]:
    """
    Clone all repos concurrently.
    Returns list of CloneResult (one per repo).
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    if dry_run:
        console.print("\n[yellow][[!]][/yellow] [bold]Dry-run mode[/bold] — no repos will be cloned.\n")
        results = []
        for repo in repos:
            console.print(f"  [dim]·[/dim] {repo['name']}  [dim]{repo['clone_url']}[/dim]")
            results.append(CloneResult(name=repo["name"], url=repo["clone_url"], status="skipped", reason="dry-run"))
        return results

    cloned_count  = 0
    skipped_count = 0
    failed_count  = 0
    results: list[CloneResult] = []

    with _make_progress() as progress:
        task: TaskID = progress.add_task(
            "Cloning",
            total=len(repos),
            status_line=f"cloned=0  skipped=0  failed=0",
        )

        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = {
                pool.submit(_clone_one, repo, output_dir, depth, retries, token): repo
                for repo in repos
            }

            for future in as_completed(futures):
                res: CloneResult = future.result()
                results.append(res)

                if res.status == "cloned":
                    cloned_count += 1
                elif res.status == "skipped":
                    skipped_count += 1
                else:
                    failed_count += 1

                progress.update(
                    task,
                    advance=1,
                    description=f"[bold]{res.name}[/bold]",
                    status_line=(
                        f"cloned=[green]{cloned_count}[/green]  "
                        f"skipped=[dim]{skipped_count}[/dim]  "
                        f"failed=[red]{failed_count}[/red]"
                    ),
                )

    return results
