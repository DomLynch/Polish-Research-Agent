# Polish Research Agent Handover

Last updated: 2026-06-10 19:55 +04

## Canonical Repo

- Local folder: `/Users/domininclynch/Desktop/Business/Polish - Research agent`
- GitHub: `https://github.com/DomLynch/Polish-Research-Agent`
- Branch: `main`
- Base package/runtime commit before this handover doc: `227a4a3`
- VPS deploy path: `/opt/researka-preflight-qa`
- Legacy local checkout still exists at `/Users/domininclynch/Desktop/Business/researka-preflight-qa`; use the canonical folder above for future commits.

## Purpose

Independent final pre-submit cleaner and QA gate for Researka research artifacts.
It runs after v3/v4 produce an artifact and before submission to Researka.

It may:
- safely clean presentation defects
- report findings (unsupported citations, overclaims, direction mismatches, M3 review) as advisories
- write machine-readable reports and cleaned payloads

It never blocks a submission. Producer checks and Researka platform review
own rejection.

Note: as of preflight-v2 the layer is advisory-only. The VPS deploy runs the
older fully-blocking build until it pulls the latest main.

It must not:
- retrieve evidence
- add citations
- decide publication
- replace Researka platform review

## Live Integrations

### v3 Research Agent

- VPS repo: `/opt/research-agent-bot`
- Current live commit checked during handover: `a4dfe5d8`
- Env file: `/etc/research-agent-bot/research-agent-bot.env`
- Live env:
  - `RESEARKA_PREFLIGHT_QA=live`
  - `RESEARKA_PREFLIGHT_QA_ROOT=/opt/researka-preflight-qa`
  - `RESEARKA_PREFLIGHT_USE_M3=1`
- Code behavior: v3 maps `live` to `enforce` in `scripts/daily_research_paper_submit.py`.
- Timers: v3 submit/fresh/revise/reconcile timers active.

### v4 Alpha Memo Agent

- VPS repo: `/root/Research-Agent-Bot-v4`
- Current live commit checked during handover: `a53b4df`
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
9 passed in 0.21s
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

- VPS v4 service venv does not have `pytest`; VPS verification uses `py_compile` plus live smoke.

## Live M3 Smoke Artifacts

Smoke semantics: the `block` rows below are intentional adversarial overclaim payloads.
`checked=false` plus `m3_status=block` is the expected passing result in enforce mode.

### v3

Path:

```text
/root/researka-v3-live-preflight-smoke/20260610T1850Z/LIVE_SMOKE_SUMMARY.json
```

Summary:

```text
pass:  checked=true,  status=pass,  m3_status=pass
block: checked=false, status=block, m3_status=block, codes=m3_block,m3_block
```

### v4

Path:

```text
/root/researka-v4-live-preflight-smoke/current-commit/LIVE_SMOKE_SUMMARY.json
```

Current regenerated summary:

```text
commit=a53b4df
env=RESEARKA_PREFLIGHT_QA=enforce, RESEARKA_PREFLIGHT_USE_M3=1
pass:  checked=true,  status=pass,  m3_status=pass
block: checked=false, status=block, m3_status=block, codes=m3_block
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
  'cd /root/Research-Agent-Bot-v4 && git rev-parse --short HEAD && git rev-parse --short @{u} && git status --short && grep -h "^RESEARKA_PREFLIGHT" .env /etc/researka-agent-v4.env && cat /root/researka-v4-live-preflight-smoke/current-commit/LIVE_SMOKE_SUMMARY.json'
```

## Known Caveats

- v4 organic service runs currently often stop before submit with `no_fresh_candidate`; this is candidate availability, not preflight failure.
- v4 VPS service venv lacks `pytest`, so v4 VPS test-file execution is not currently available without installing test tooling.
- There is an unrelated local v3 stash:
  `stash@{0}: preflight-review preserve local v3 test WIP 2026-06-10`.
  It concerns fresh-lane retry tests, not polish/preflight integration.
