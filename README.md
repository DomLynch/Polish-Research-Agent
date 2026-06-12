# Polish Research Agent

Independent final pre-submit cleaner and QA gate for Researka research artifacts.

## Purpose

This package runs after v3/v4 producers finish an artifact and before anything is submitted to Researka. It is fix-first and improve-only: a fixable finding gets repaired (safe presentation cleanup, plus a standard limitation caveat when a narrow-signal artifact lacks one), and only findings it cannot safely fix (unsupported citations, overclaims, M3 review) are reported as advisories — warnings for the producer and downstream review. It never blocks a submission — producer checks and Researka platform review own rejection. If a fix would alter protected content (numbers, citations, title, or any existing hedge), the original text is shipped untouched instead. It does not retrieve sources, add citations, decide publication, or replace the Researka gatekeeper.

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
