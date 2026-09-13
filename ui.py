"""
ui.py — Rich-based terminal UI for Defaultclone.
All styling lives here; import from this module elsewhere.
"""

from __future__ import annotations

from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich import box

# ── Theme ────────────────────────────────────────────────────────────────────

THEME = Theme(
    {
        "banner":    "bold red",
        "header":    "bold red",
        "info":      "bright_white",
        "warn":      "bold yellow",
        "error":     "bold red",
        "success":   "bold green",
        "muted":     "dim white",
        "bar.back":  "on grey11",
        "bar.fill":  "red",
        "bar.pulse": "bright_red",
    }
)

console = Console(theme=THEME, highlight=False)

# ── ASCII banner ─────────────────────────────────────────────────────────────

BANNER = r"""
██████╗ ███████╗███████╗ █████╗ ██╗   ██╗██╗  ████████╗ ██████╗██╗      ██████╗ ███╗   ██╗███████╗
██╔══██╗██╔════╝██╔════╝██╔══██╗██║   ██║██║  ╚══██╔══╝██╔════╝██║     ██╔═══██╗████╗  ██║██╔════╝
██║  ██║█████╗  █████╗  ███████║██║   ██║██║     ██║   ██║     ██║     ██║   ██║██╔██╗ ██║█████╗
██║  ██║██╔══╝  ██╔══╝  ██╔══██║██║   ██║██║     ██║   ██║     ██║     ██║   ██║██║╚██╗██║██╔══╝
██████╔╝███████╗██║     ██║  ██║╚██████╔╝███████╗██║   ╚██████╗███████╗╚██████╔╝██║ ╚████║███████╗
╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝    ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
"""

BANNER_SMALL = "[ DEFAULTCLONE ]  —  Bulk GitHub Repo Cloner"


def print_banner() -> None:
    """Print the startup ASCII banner."""
    try:
        console.print(BANNER, style="banner", highlight=False)
    except Exception:
        console.rule(BANNER_SMALL, style="header")
    console.print(
        "  Bulk GitHub Repo Cloner  |  OSINT / Recon Toolkit\n",
        style="muted",
        justify="center",
    )


# ── Prefix helpers ────────────────────────────────────────────────────────────

def info(msg: str) -> None:
    console.print(f"[info][[+]][/info] {msg}")


def warn(msg: str) -> None:
    console.print(f"[warn][[!]][/warn] {msg}")


def error(msg: str) -> None:
    console.print(f"[error][[-]][/error] {msg}")


def success(msg: str) -> None:
    console.print(f"[success][[+]][/success] {msg}")


# ── Repo discovery summary ────────────────────────────────────────────────────

def print_discovery_summary(
    target: str,
    account_type: str,
    total_found: int,
    forks_excluded: int,
    repos_to_clone: int,
    estimated_seconds: float,
) -> None:
    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="red",
        show_header=False,
        padding=(0, 2),
    )
    table.add_column("Key",   style="dim white", no_wrap=True)
    table.add_column("Value", style="bright_white")

    mins, secs = divmod(int(estimated_seconds), 60)
    eta_str = f"~{mins}m {secs}s" if mins else f"~{secs}s"

    table.add_row("Target",            f"{target}  [dim]({account_type})[/dim]")
    table.add_row("Repos found",       str(total_found))
    table.add_row("Forks excluded",    str(forks_excluded))
    table.add_row("Repos to clone",    str(repos_to_clone))
    table.add_row("Estimated time",    eta_str)

    console.print(
        Panel(table, title="[header]  Discovery  [/header]", border_style="red", expand=False)
    )


# ── Final summary table ───────────────────────────────────────────────────────

def print_final_summary(
    total: int,
    cloned: int,
    skipped: int,
    failed: int,
    elapsed: float,
    output_path: str,
    token_hint: str | None,
) -> None:
    table = Table(
        box=box.SIMPLE_HEAVY,
        border_style="red",
        show_header=False,
        padding=(0, 2),
    )
    table.add_column("Key",   style="dim white", no_wrap=True)
    table.add_column("Value", style="bright_white")

    mins, secs = divmod(int(elapsed), 60)
    elapsed_str = f"{mins}m {secs}s" if mins else f"{secs}s"

    table.add_row("Total repos",  str(total))
    table.add_row("Cloned",       f"[success]{cloned}[/success]")
    table.add_row("Skipped",      f"[muted]{skipped}[/muted]")
    table.add_row("Failed",       f"[error]{failed}[/error]" if failed else "0")
    table.add_row("Time taken",   elapsed_str)
    table.add_row("Output path",  output_path)
    if token_hint:
        table.add_row("Token used",   f"[muted]{token_hint}[/muted]")

    console.print(
        Panel(table, title="[header]  Summary  [/header]", border_style="red", expand=False)
    )


# ── Mask a token for display ──────────────────────────────────────────────────

def mask_token(token: str) -> str:
    """Return a masked representation — first 4 prefix chars + **** + last 4."""
    if not token or len(token) < 10:
        return "****"
    return f"{token[:4]}****{token[-4:]}"
