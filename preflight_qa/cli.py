from __future__ import annotations

import argparse
import json
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
        return 0 if report["status"] == "pass" else 2
    return 2


def _read_json(path: Path) -> Json:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit(f"expected JSON object: {path}")
    return data


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
