# DEFAULTCLONE

> Bulk GitHub repo cloner for OSINT / recon use.

```
██████╗ ███████╗███████╗ █████╗ ██╗   ██╗██╗  ████████╗ ██████╗██╗      ██████╗ ███╗   ██╗███████╗
██╔══██╗██╔════╝██╔════╝██╔══██╗██║   ██║██║  ╚══██╔══╝██╔════╝██║     ██╔═══██╗████╗  ██║██╔════╝
██║  ██║█████╗  █████╗  ███████║██║   ██║██║     ██║   ██║     ██║     ██║   ██║██╔██╗ ██║█████╗
██║  ██║██╔══╝  ██╔══╝  ██╔══██║██║   ██║██║     ██║   ██║     ██║     ██║   ██║██║╚██╗██║██╔══╝
██████╔╝███████╗██║     ██║  ██║╚██████╔╝███████╗██║   ╚██████╗███████╗╚██████╔╝██║ ╚████║███████╗
╚═════╝ ╚══════╝╚═╝     ╚═╝  ╚═╝ ╚═════╝ ╚══════╝╚═╝    ╚═════╝╚══════╝ ╚═════╝ ╚═╝  ╚═══╝╚══════╝
```

Given a GitHub username or organization name, Defaultclone:

1. Fetches **all** public (and optionally private) repositories
2. Prints a repo count + estimated time
3. Clones everything concurrently with a live Rich progress bar
4. Writes `report.json` and `report.log` summarising the run

---

## Requirements

- Python 3.11+
- `git` in `PATH`

---

## Installation

```bash
git clone https://github.com/yourhandle/defaultclone
cd defaultclone
pip install -r requirements.txt
```

---

## First Run — Token Setup

On first launch, Defaultclone will prompt you for a GitHub Personal Access Token if none is saved:

```
[!] No GitHub token found.
    Without a token you are limited to 60 API requests/hour.
    Press Enter to skip, or paste a token to save it.
  Token (Enter to skip):
```

Your token is stored at `~/.defaultclone/config.json` with permissions `600` (owner-read/write only on POSIX). It is **never** printed to the terminal or written to report files.

To generate a token: <https://github.com/settings/tokens> — classic token with `repo` scope is sufficient.

---

## Usage Examples

```bash
# Clone all public repos for a user
python defaultclone.py torvalds

# Clone all repos for a GitHub org
python defaultclone.py microsoft

# Include forked repos
python defaultclone.py someuser --include-forks

# Shallow clone (last 1 commit only, much faster)
python defaultclone.py someorg --depth 1

# Custom output directory
python defaultclone.py someuser --output /data/recon

# Skip confirmation prompt
python defaultclone.py someuser --yes

# Dry-run (list repos, don't clone)
python defaultclone.py someuser --dry-run

# Increase parallelism (max 10)
python defaultclone.py someorg --concurrency 10

# Use a token just for this run (not saved)
python defaultclone.py someuser --token ghp_xxxx

# Use environment variable (not saved)
GITHUB_TOKEN=ghp_xxxx python defaultclone.py someuser

# Use env/flag token AND save it
python defaultclone.py someuser --token ghp_xxxx --save-token
```

---

## Token Management

| Command | Effect |
|---|---|
| `python defaultclone.py --set-token` | Re-prompt and overwrite saved token |
| `python defaultclone.py --logout` | Delete the saved token |
| `--token TOKEN` | Override for this run only |
| `GITHUB_TOKEN=xxx` | Override via env var (this run only) |
| `--token TOKEN --save-token` | Override and persist |

---

## Flag Reference

```
positional:
  target                GitHub username or organization name

token management:
  --token TOKEN         One-time token override (not auto-saved)
  --save-token          Persist the provided/entered token
  --set-token           Force re-prompt, overwrite saved token
  --logout              Delete saved token

clone options:
  --output DIR          Output base directory (default: ./cloned)
  --concurrency N       Parallel clone threads (default: 5, max: 10)
  --depth N             Shallow clone depth (default: full clone)
  --include-forks       Include forked repos (default: excluded)
  --retry N             Retry failed clones N times (default: 1)

behaviour:
  --dry-run             List repos and count; don't clone
  --yes, -y             Skip confirmation prompt
```

---

## Output Structure

```
cloned/
└── <target>/
    ├── repo-one/          ← cloned repo
    ├── repo-two/
    ├── …
    ├── report.json        ← machine-readable summary
    └── report.log         ← human-readable log
```

`report.json` contains clone status per repo (cloned / skipped / failed with reason). Your token **never** appears in these files.

---

## Architecture

| File | Responsibility |
|---|---|
| `defaultclone.py` | Entry point, CLI parsing, orchestration |
| `auth.py` | Token prompt, save/load/validate, config |
| `github_api.py` | Repo listing, pagination, rate-limit handling |
| `cloner.py` | Threaded git clone, retry, skip logic |
| `ui.py` | Rich banner, progress bar, tables, theme |
| `report.py` | Writes `report.json` / `report.log` |

---

## Rate Limits

| Scenario | Limit |
|---|---|
| No token | 60 requests / hour |
| With token | 5 000 requests / hour |

If you hit the limit, Defaultclone prints the reset time and suggests adding a token.

---

## Legal / Ethics

This tool is for authorized security research, OSINT, and archival purposes only. Only target accounts and repositories you have permission to access. The authors accept no responsibility for misuse.
