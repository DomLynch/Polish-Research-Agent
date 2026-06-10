# Polish Research Agent

Independent final pre-submit cleaner and QA gate for Researka research artifacts.

## Purpose

This package runs after v3/v4 producers finish an artifact and before anything is submitted to Researka. It is improve-only and advisory-only: it applies safe presentation cleanup and reports every finding (unsupported citations, overclaims, M3 review) as an advisory. It never blocks a submission — producer checks and Researka platform review own rejection. If cleanup would alter protected content (numbers, citations, hedges, title), the original text is shipped untouched instead. It does not retrieve sources, add citations, decide publication, or replace the Researka gatekeeper.

## CLI

```bash
python -m preflight_qa check --input payload.json --out report.json --clean-out cleaned_payload.json
```

Exit codes:
- `0`: always (advisory-only; findings are in the report's `advisories`)

Optional MiniMax-M3 semantic review:

```bash
RESEARKA_PREFLIGHT_USE_M3=1 MINIMAX_API_KEY=... python -m preflight_qa check --input payload.json --out report.json --clean-out cleaned_payload.json --use-m3
```

M3 review is advisory only: its findings are recorded in the report's `advisories` and never block or clear anything.

## Integration

Producer repos call this in the final pre-submit step with:

```bash
RESEARKA_PREFLIGHT_QA=off|shadow|enforce
RESEARKA_PREFLIGHT_QA_ROOT=/opt/researka-preflight-qa
```

Default mode is `off`.
