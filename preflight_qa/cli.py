from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

from .core import run_preflight

Json = dict[str, Any]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="preflight-qa")
    sub = parser.add_subparsers(dest="cmd", required=True)
    check = sub.add_parser("check")
    check.add_argument("--input", required=True)
    check.add_argument("--out", required=True)
    check.add_argument("--clean-out", default="")
    check.add_argument("--use-m3", action="store_true")
    args = parser.parse_args(argv)
    if args.cmd == "check":
        payload = _read_json(Path(args.input))
        report = run_preflight(payload, use_m3=args.use_m3)
        cleaned = report.get("cleaned_payload")
        compact = dict(report)
        compact.pop("cleaned_payload", None)
        _write_json(Path(args.out), compact)
        if args.clean_out and isinstance(cleaned, dict):
            _write_json(Path(args.clean_out), cleaned)
        _emit_metrics(report)
        return 0 if report["status"] == "pass" else 2
    return 2


def _emit_metrics(report: Json) -> None:
    """Surface per-run outcome so the M3 failure rate is visible without grepping reports.

    Always logs one line to stderr; also appends JSONL to PREFLIGHT_METRICS_LOG when set.
    """
    record = {
        "ts": round(time.time(), 3),
        "qa_version": report.get("qa_version"),
        "status": report.get("status"),
        "m3": (report.get("m3_result") or {}).get("status"),
        "fixes": report.get("safe_fixes_applied") or [],
        "advisories": [a.get("code") for a in report.get("advisories") or []],
    }
    line = json.dumps(record, sort_keys=True)
    print(f"preflight_qa {line}", file=sys.stderr)
    path = os.getenv("PREFLIGHT_METRICS_LOG")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as handle:
                handle.write(line + "\n")
        except OSError:
            pass


def _read_json(path: Path) -> Json:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
