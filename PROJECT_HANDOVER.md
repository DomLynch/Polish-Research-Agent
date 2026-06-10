# Polish Research Agent Handover

Last updated: 2026-06-10 19:55 +04

## Canonical Repo

- Local folder: `/Users/domininclynch/Desktop/Business/Polish - Research agent`
- GitHub: `https://github.com/DomLynch/Polish-Research-Agent`
- Branch: `main`
- Current package commit checked during cleanup: `dbe6f6a`
- VPS deploy path: `/opt/researka-preflight-qa`
- Legacy local checkout still exists at `/Users/domininclynch/Desktop/Business/researka-preflight-qa`; use the canonical folder above for future commits.

## Purpose

Independent final pre-submit polish-and-report layer for Researka research artifacts.
It runs after v3/v4 produce an artifact and before submission to Researka.

It may:
- safely clean presentation defects
- report findings (unsupported citations, overclaims, direction mismatches, M3 review) as advisories
- write machine-readable reports and cleaned payloads

It never blocks a submission. If cleaning would change protected content,
the original payload is shipped untouched and the reason is reported. Producer
checks and Researka platform review own rejection.

It must not:
- retrieve evidence
- add citations
- decide publication
- replace Researka platform review

## Live Integrations

### v3 Research Agent

- VPS repo: `/opt/research-agent-bot`
- Current live commit checked during cleanup: `9aa2c0df`
- Env file: `/etc/research-agent-bot/research-agent-bot.env`
- Live env:
  - `RESEARKA_PREFLIGHT_QA=live`
  - `RESEARKA_PREFLIGHT_QA_ROOT=/opt/researka-preflight-qa`
  - `RESEARKA_PREFLIGHT_USE_M3=1`
- Code behavior: v3 maps `live` to `enforce` in `scripts/daily_research_paper_submit.py`.
- Timers: v3 submit/fresh/revise/reconcile timers active.

### v4 Alpha Memo Agent

- VPS repo: `/root/Research-Agent-Bot-v4`
- Current live commit checked during cleanup: `50ea754`
- Env files:
  - `/root/Research-Agent-Bot-v4/.env`
  - `/etc/researka-agent-v4.env`
- Live env in both files:
  - `RESEARKA_PREFLIGHT_QA=enforce`
  - `RESEARKA_PREFLIGHT_QA_ROOT=/opt/researka-preflight-qa`
  - `RESEARKA_PREFLIGHT_USE_M3=1`
- Timers: v4 alpha timers active.
- Last organic v4 AI service checks reached the service path but stopped at `no_fresh_candidate`, so they did not naturally exercise submit/preflight.

## Verification Evidence

### Polish Package

Run from canonical local folder:

```bash
cd "/Users/domininclynch/Desktop/Business/Polish - Research agent"
python3 -m pytest -q
```

Observed:

```text
15 passed
```

### v3 Focused Tests

Local and VPS focused preflight tests passed:

```text
5 passed
```

### v4 Focused Tests

- Tracked v4 test file: `tests/test_preflight_submit_hook.py`
- Added and pushed in v4 commit `17980ae`, still present in later live v4 commits.
- Local checks:

```text
ruff: All checks passed
mypy: Success: no issues found in 1 source file
pytest: 2 passed
```

- VPS v4 service venv historically lacked `pytest`; if unavailable, use `py_compile`
  plus live smoke and run pytest locally.

## Live M3 Smoke Artifacts

Smoke semantics: adversarial overclaim payloads should be submitted onward with
`status=pass`, advisory codes, and `m3_status=block` in the report.

### v3

Path:

```text
/root/researka-v3-live-preflight-smoke/advisory-current/LIVE_SMOKE_SUMMARY.json
```

Summary:

```text
clean:    checked=true, status=pass, m3_status=pass, advisories=[]
advisory: checked=true, status=pass, m3_status=pass, advisories=[doi_not_in_source_bundle]
```

### v4

Path:

```text
/root/researka-v4-live-preflight-smoke/advisory-current/LIVE_SMOKE_SUMMARY.json
```

Current regenerated summary:

```text
commit=50ea754
env=RESEARKA_PREFLIGHT_QA=enforce, RESEARKA_PREFLIGHT_USE_M3=1
clean:    checked=true, status=pass, m3_status=pass, advisories=[]
advisory: checked=true, status=pass, m3_status=block, advisories=[doi_not_in_source_bundle,m3_block]
```

## Commands For Claude Audit

```bash
# Polish package
cd "/Users/domininclynch/Desktop/Business/Polish - Research agent"
git remote -v
git rev-parse --short HEAD
git status --short
python3 -m pytest -q

# VPS polish deploy
ssh -i ~/.ssh/binance_futures_tool root@100.96.74.1 \
  'cd /opt/researka-preflight-qa && git rev-parse --short HEAD && git status --short'

# v3 live env + tests
ssh -i ~/.ssh/binance_futures_tool root@100.96.74.1 \
  'cd /opt/research-agent-bot && git rev-parse --short HEAD && git status --short && grep -n "^RESEARKA_PREFLIGHT" /etc/research-agent-bot/research-agent-bot.env && .venv/bin/python -m pytest -q tests/test_preflight_submit_hook.py'

# v4 live env + smoke
ssh -i ~/.ssh/binance_futures_tool root@100.96.74.1 \
  'cd /root/Research-Agent-Bot-v4 && git rev-parse --short HEAD && git rev-parse --short @{u} && git status --short && grep -h "^RESEARKA_PREFLIGHT" .env /etc/researka-agent-v4.env && cat /root/researka-v4-live-preflight-smoke/advisory-current/LIVE_SMOKE_SUMMARY.json'
```

## Known Caveats

- v4 organic service runs currently often stop before submit with `no_fresh_candidate`; this is candidate availability, not preflight failure.
- v4 VPS service venv lacks `pytest`, so v4 VPS test-file execution is not currently available without installing test tooling.
- There is an unrelated local v3 stash:
  `stash@{0}: preflight-review preserve local v3 test WIP 2026-06-10`.
  It concerns fresh-lane retry tests, not polish/preflight integration.
