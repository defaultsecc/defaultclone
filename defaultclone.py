#!/usr/bin/env python3
"""
defaultclone.py — Entry point for Defaultclone bulk GitHub repo cloner.
Usage: python defaultclone.py <target> [options]
"""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

# ── Ensure local modules resolve regardless of cwd ────────────────────────────
sys.path.insert(0, str(Path(__file__).parent))

from auth import delete_token, resolve_token
from cloner import clone_all
from github_api import count_forks, fetch_repos, resolve_account_type
from report import write_reports
from ui import (
    console,
    error,
    info,
    mask_token,
    print_banner,
    print_discovery_summary,
    print_final_summary,
    warn,
)

# ── Rough time estimator (seconds per repo, heuristic) ───────────────────────
_SECS_PER_REPO = 8.0   # rough average for a medium-sized repo


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="defaultclone",
        description="Bulk GitHub repo cloner for OSINT / recon.",
        formatter_class=argparse.RawTextHelpFormatter,
    )

    p.add_argument(
        "target",
        nargs="?",
        help="GitHub username or organization name.",
    )

    # Token management
    tok_group = p.add_argument_group("Token management")
    tok_group.add_argument(
        "--token",
        metavar="TOKEN",
        help="One-time token override (not auto-saved).",
    )
    tok_group.add_argument(
        "--save-token",
        action="store_true",
        help="Persist the provided/entered token to config.",
    )
    tok_group.add_argument(
        "--set-token",
        action="store_true",
        help="Force re-prompt and overwrite saved token.",
    )
    tok_group.add_argument(
        "--logout",
        "--clear-token",
        dest="logout",
        action="store_true",
        help="Delete saved token from config.",
    )

    # Clone options
    clone_group = p.add_argument_group("Clone options")
    clone_group.add_argument(
        "--output",
        metavar="DIR",
        default="./cloned",
        help="Output base directory (default: ./cloned).",
    )
    clone_group.add_argument(
        "--concurrency",
        metavar="N",
        type=int,
        default=5,
        help="Parallel clone threads (default: 5, max: 10).",
    )
    clone_group.add_argument(
        "--depth",
        metavar="N",
        type=int,
        default=None,
        help="Shallow clone depth (default: full clone).",
    )
    clone_group.add_argument(
        "--include-forks",
        action="store_true",
        help="Include forked repos (default: excluded).",
    )
    clone_group.add_argument(
        "--retry",
        metavar="N",
        type=int,
        default=1,
        help="Retry failed clones N times (default: 1).",
    )

    # Behaviour flags
    beh_group = p.add_argument_group("Behaviour")
    beh_group.add_argument(
        "--dry-run",
        action="store_true",
        help="List repos and show count; don't clone.",
    )
    beh_group.add_argument(
        "--yes",
        "-y",
        action="store_true",
        help="Skip confirmation prompt.",
    )

    return p


def main() -> None:
    print_banner()
    parser = _build_parser()
    args   = parser.parse_args()

    # ── --logout / --clear-token ──────────────────────────────────────────────
    if args.logout:
        delete_token()
        sys.exit(0)

    # ── --set-token (no target required) ─────────────────────────────────────
    if args.set_token and not args.target:
        resolve_token(set_token=True)
        sys.exit(0)

    # ── Target is required for everything else ────────────────────────────────
    if not args.target:
        parser.print_help()
        sys.exit(1)

    target = args.target.strip()

    # ── Clamp concurrency ─────────────────────────────────────────────────────
    concurrency = max(1, min(args.concurrency, 10))
    if args.concurrency != concurrency:
        warn(f"Concurrency clamped to {concurrency} (max 10).")

    # ── Token resolution ──────────────────────────────────────────────────────
    env_token = os.environ.get("GITHUB_TOKEN", "").strip() or None
    token = resolve_token(
        cli_token   = args.token,
        env_token   = env_token,
        set_token   = args.set_token,
        save_flag   = args.save_token,
    )

    # ── Discover account type ─────────────────────────────────────────────────
    info(f"Resolving target: [bold]{target}[/bold]")
    account_type = resolve_account_type(target, token)
    info(f"Account type: [bold]{account_type}[/bold]")

    # ── Fetch all repos ───────────────────────────────────────────────────────
    info("Fetching repository list …")

    # Fetch with forks to get accurate fork count for summary
    all_repos_with_forks = fetch_repos(
        target, account_type, token, include_forks=True
    )
    forks_count = count_forks(all_repos_with_forks)

    if args.include_forks:
        repos_to_clone = all_repos_with_forks
    else:
        repos_to_clone = [r for r in all_repos_with_forks if not r.get("fork", False)]

    total_found = len(all_repos_with_forks)
    clone_count = len(repos_to_clone)

    if total_found == 0:
        warn(f"No public repos found for '{target}'.")
        sys.exit(0)

    # ── Estimate ──────────────────────────────────────────────────────────────
    estimated_seconds = (clone_count / max(concurrency, 1)) * _SECS_PER_REPO

    # ── Discovery summary ─────────────────────────────────────────────────────
    console.print()
    print_discovery_summary(
        target           = target,
        account_type     = account_type,
        total_found      = total_found,
        forks_excluded   = 0 if args.include_forks else forks_count,
        repos_to_clone   = clone_count,
        estimated_seconds = estimated_seconds,
    )

    # ── Confirmation ──────────────────────────────────────────────────────────
    if not args.yes and not args.dry_run:
        console.print()
        try:
            answer = input("  Proceed? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[red][[-]][/red] Aborted.")
            sys.exit(1)
        if answer not in ("", "y", "yes"):
            info("Aborted by user.")
            sys.exit(0)

    # ── Output directory ──────────────────────────────────────────────────────
    output_base = Path(args.output).expanduser().resolve()
    output_dir  = output_base / target
    info(f"Output directory: [dim]{output_dir}[/dim]")
    console.print()

    # ── Clone ─────────────────────────────────────────────────────────────────
    start_time = time.monotonic()

    results = clone_all(
        repos       = repos_to_clone,
        output_dir  = output_dir,
        depth       = args.depth,
        concurrency = concurrency,
        retries     = args.retry,
        token       = token,
        dry_run     = args.dry_run,
    )

    elapsed = time.monotonic() - start_time

    # ── Final summary ─────────────────────────────────────────────────────────
    cloned_n  = sum(1 for r in results if r.status == "cloned")
    skipped_n = sum(1 for r in results if r.status == "skipped")
    failed_n  = sum(1 for r in results if r.status == "failed")

    console.print()
    print_final_summary(
        total       = clone_count,
        cloned      = cloned_n,
        skipped     = skipped_n,
        failed      = failed_n,
        elapsed     = elapsed,
        output_path = str(output_dir),
        token_hint  = mask_token(token) if token else None,
    )

    # ── Reports ───────────────────────────────────────────────────────────────
    if not args.dry_run:
        write_reports(
            output_dir   = output_dir,
            target       = target,
            account_type = account_type,
            results      = results,
            elapsed      = elapsed,
        )

    # ── Exit code ─────────────────────────────────────────────────────────────
    sys.exit(1 if failed_n > 0 else 0)


if __name__ == "__main__":
    main()
