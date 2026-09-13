"""
github_api.py — GitHub REST API interaction for Defaultclone.
Handles repo discovery, pagination, and rate-limit responses.
"""

from __future__ import annotations

import sys
import time
from datetime import datetime, timezone
from typing import Optional

import requests

from auth import auth_headers
from ui import info, warn, error

# ── Constants ─────────────────────────────────────────────────────────────────

BASE = "https://api.github.com"
PER_PAGE = 100


# ── Internal helpers ──────────────────────────────────────────────────────────

def _session(token: Optional[str]) -> requests.Session:
    s = requests.Session()
    s.headers.update(auth_headers(token))
    return s


def _handle_rate_limit(response: requests.Response) -> None:
    """If we've hit a primary rate limit, print reset time and exit."""
    remaining = response.headers.get("X-RateLimit-Remaining", "?")
    reset_ts   = response.headers.get("X-RateLimit-Reset")
    if remaining == "0" or response.status_code == 403:
        if reset_ts:
            try:
                reset_dt = datetime.fromtimestamp(int(reset_ts), tz=timezone.utc)
                reset_str = reset_dt.strftime("%H:%M:%S UTC")
            except (ValueError, OSError):
                reset_str = "unknown"
        else:
            reset_str = "unknown"
        error(
            f"GitHub API rate limit exceeded.\n"
            f"    Resets at: {reset_str}\n"
            f"    Tip: add or set a token with [bold]--set-token[/bold] for 5 000 req/hr."
        )
        sys.exit(1)


def _get_json(session: requests.Session, url: str, params: dict | None = None) -> dict | list:
    """GET a single URL; handle errors and rate limits."""
    resp = session.get(url, params=params, timeout=20)
    if resp.status_code == 403:
        _handle_rate_limit(resp)
    if resp.status_code == 404:
        error(f"Not found: {url}")
        sys.exit(1)
    resp.raise_for_status()
    return resp.json()


# ── Public API ────────────────────────────────────────────────────────────────

def resolve_account_type(target: str, token: Optional[str]) -> str:
    """
    Return 'User' or 'Organization' for a given GitHub handle.
    Exits with a clear message if the target doesn't exist.
    """
    session = _session(token)
    try:
        data = _get_json(session, f"{BASE}/users/{target}")
    except requests.HTTPError as exc:
        error(f"Could not resolve target '{target}': {exc}")
        sys.exit(1)
    t = data.get("type", "User")
    return "Organization" if t == "Organization" else "User"


def fetch_repos(
    target: str,
    account_type: str,
    token: Optional[str],
    include_forks: bool = False,
) -> list[dict]:
    """
    Paginate through all repositories for target.
    Returns list of repo dicts (raw GitHub API objects).
    Forks are included or excluded based on include_forks.
    """
    session = _session(token)
    repos: list[dict] = []
    page = 1

    if account_type == "Organization":
        endpoint = f"{BASE}/orgs/{target}/repos"
        params_base = {"type": "public", "per_page": PER_PAGE}
    else:
        endpoint = f"{BASE}/users/{target}/repos"
        params_base = {"type": "owner", "per_page": PER_PAGE}

    # If token is present, also fetch private repos
    if token and account_type == "User":
        params_base["visibility"] = "all"
        params_base.pop("type", None)

    while True:
        params = {**params_base, "page": page}
        try:
            data = _get_json(session, endpoint, params=params)
        except requests.HTTPError as exc:
            error(f"API error fetching repos page {page}: {exc}")
            sys.exit(1)

        if not isinstance(data, list) or not data:
            break

        repos.extend(data)
        if len(data) < PER_PAGE:
            break
        page += 1
        # Be a good citizen — small pause between pages
        time.sleep(0.1)

    if not include_forks:
        repos = [r for r in repos if not r.get("fork", False)]

    return repos


def count_forks(all_repos: list[dict]) -> int:
    """Count how many repos in a full list are forks."""
    return sum(1 for r in all_repos if r.get("fork", False))
