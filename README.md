# Polish Research Agent

Independent final pre-submit cleaner and QA gate for Researka research artifacts.

## Purpose

This package runs after v3/v4 producers finish an artifact and before anything is submitted to Researka. It can apply safe presentation cleanup and block unsafe artifacts. It does not retrieve sources, add citations, decide publication, or replace the Researka gatekeeper.

## CLI

```bash
python -m preflight_qa check --input payload.json --out report.json --clean-out cleaned_payload.json
```

Exit codes:
- `0`: pass
- `2`: block

Optional MiniMax-M3 semantic review:

```bash
RESEARKA_PREFLIGHT_USE_M3=1 MINIMAX_API_KEY=... python -m preflight_qa check --input payload.json --out report.json --clean-out cleaned_payload.json --use-m3
```

M3 can add a block but cannot clear deterministic blocks.

## Integration

Producer repos call this in the final pre-submit step with:

```bash
RESEARKA_PREFLIGHT_QA=off|shadow|enforce
RESEARKA_PREFLIGHT_QA_ROOT=/opt/researka-preflight-qa
```

Default mode is `off`.
