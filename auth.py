"""
auth.py — GitHub token management for Defaultclone.
Handles prompt, persist, load, validate, and revoke.
"""

from __future__ import annotations

import json
import os
import stat
import sys
from getpass import getpass
from pathlib import Path
from typing import Optional

import requests

from ui import console, info, warn, error

# ── Paths ─────────────────────────────────────────────────────────────────────

CONFIG_DIR  = Path.home() / ".defaultclone"
CONFIG_FILE = CONFIG_DIR / "config.json"

# ── Internal helpers ──────────────────────────────────────────────────────────

def _load_config() -> dict:
    if not CONFIG_FILE.exists():
        return {}
    try:
        with CONFIG_FILE.open() as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_config(data: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with CONFIG_FILE.open("w") as f:
        json.dump(data, f, indent=2)
    # POSIX: restrict to owner read/write only
    if os.name == "posix":
        CONFIG_FILE.chmod(stat.S_IRUSR | stat.S_IWUSR)


# ── Public API ────────────────────────────────────────────────────────────────

def get_saved_token() -> Optional[str]:
    """Return the token stored in config, or None."""
    return _load_config().get("github_token")


def save_token(token: str) -> None:
    """Persist token to config file."""
    cfg = _load_config()
    cfg["github_token"] = token
    _save_config(cfg)
    info(f"Token saved to [dim]{CONFIG_FILE}[/dim]")


def delete_token() -> None:
    """Remove token from config file (--logout / --clear-token)."""
    if not CONFIG_FILE.exists():
        warn("No saved token found.")
        return
    cfg = _load_config()
    if "github_token" in cfg:
        del cfg["github_token"]
        _save_config(cfg)
        info("Saved token deleted.")
    else:
        warn("No saved token found in config.")


def prompt_for_token(prompt_msg: str = "Paste your GitHub Personal Access Token") -> str:
    """Prompt user for a token (hidden input). Returns the token string."""
    console.print(f"\n[yellow][[!]][/yellow] {prompt_msg}:")
    try:
        token = getpass("  Token: ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[red][[-]][/red] Aborted.")
        sys.exit(1)
    if not token:
        error("No token provided.")
        sys.exit(1)
    return token


def validate_token(token: str) -> bool:
    """
    Validate a GitHub token with a lightweight API call.
    Returns True if valid, False otherwise.
    Never prints the token.
    """
    try:
        resp = requests.get(
            "https://api.github.com/rate_limit",
            headers=_auth_headers(token),
            timeout=10,
        )
        if resp.status_code == 200:
            return True
        if resp.status_code == 401:
            return False
        # Other codes (e.g. 403 for secondary limit) — treat as valid for now
        return resp.status_code not in (401,)
    except requests.RequestException as exc:
        warn(f"Token validation network error: {exc}")
        return False


def resolve_token(
    cli_token: Optional[str] = None,
    env_token: Optional[str] = None,
    set_token: bool = False,
    save_flag: bool = False,
) -> Optional[str]:
    """
    Determine which token to use, following priority rules:
      1. --set-token  → prompt, overwrite saved
      2. --token / GITHUB_TOKEN env  → use for this run, don't persist
         (unless --save-token also passed)
      3. Saved config token (validated)
      4. No token → run unauthenticated (public repos only, 60 req/hr)

    Returns the resolved token string, or None.
    """

    # ── Force re-prompt and save ──────────────────────────────────────────────
    if set_token:
        token = prompt_for_token("Enter a new GitHub Personal Access Token to save")
        if not validate_token(token):
            error("Token validation failed — token not saved.")
            sys.exit(1)
        save_token(token)
        info("Token updated and validated.")
        return token

    # ── Explicit override (CLI flag or env var) ───────────────────────────────
    override = cli_token or env_token
    if override:
        if not validate_token(override):
            warn("Provided token appears invalid or expired.")
        if save_flag:
            save_token(override)
            info("Override token persisted.")
        else:
            info("Using provided token for this run only (not saved).")
        return override

    # ── Saved config token ────────────────────────────────────────────────────
    saved = get_saved_token()
    if saved:
        if validate_token(saved):
            info("Loaded saved token from config (validated).")
            return saved
        else:
            warn("Saved token is invalid or expired — re-prompting.")
            token = prompt_for_token("Enter a new GitHub Personal Access Token")
            if not validate_token(token):
                error("New token also failed validation. Proceeding unauthenticated.")
                return None
            save_token(token)
            return token

    # ── First run — prompt and offer to save ──────────────────────────────────
    console.print(
        "\n[yellow][[!]][/yellow] No GitHub token found.\n"
        "    Without a token you are limited to [bold]60 API requests/hour[/bold] and\n"
        "    cannot access private repos.\n"
        "    Press [bold]Enter[/bold] to skip, or paste a token to save it."
    )
    try:
        token = getpass("  Token (Enter to skip): ").strip()
    except (EOFError, KeyboardInterrupt):
        console.print("\n[red][[-]][/red] Aborted.")
        sys.exit(1)

    if not token:
        warn("Proceeding without a token (public repos only).")
        return None

    if not validate_token(token):
        warn("Token validation failed — continuing unauthenticated.")
        return None

    save_token(token)
    return token


# ── Header helper (used by github_api.py) ────────────────────────────────────

def _auth_headers(token: Optional[str] = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def auth_headers(token: Optional[str] = None) -> dict:
    return _auth_headers(token)
