from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from preflight_qa.core import run_preflight


def _payload(body: str, *, abstract: str = "This may be limited.", sources: list[dict] | None = None) -> dict:
    return {
        "artifact_type": "alpha_memo",
        "title": "Bounded memo",
        "abstract": abstract,
        "markdown": body,
        "source_bundle": sources or [{"title": "Limited trial", "doi": "10.1000/abc", "excerpt": "limited signal"}],
    }


def test_duplicate_paragraph_is_cleaned_without_blocking() -> None:
    body = "## Result\n\nThis may be limited.\n\nThis may be limited."
    report = run_preflight(_payload(body))
    assert report["status"] == "pass"
    assert report["safe_fixes_applied"] == ["remove_duplicate_paragraph"]
    assert report["cleaned_body_markdown"].count("This may be limited.") == 1


def test_missing_doi_blocks_submit() -> None:
    report = run_preflight(_payload("This may cite DOI 10.9999/missing."))
    assert report["status"] == "block"
    assert {r["code"] for r in report["blocked_reasons"]} == {"doi_not_in_source_bundle"}


def test_positive_abstract_over_null_evidence_blocks() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe claim is supported.",
        abstract="The evidence shows strong positive benefit.",
        sources=[{"title": "Null trial", "excerpt": "no effect and not significant"}],
    ))
    assert report["status"] == "block"
    assert "abstract_results_direction_mismatch" in {r["code"] for r in report["blocked_reasons"]}


def test_m3_can_add_block_but_not_needed_for_pass() -> None:
    def reviewer(_payload: dict) -> dict:
        return {
            "status": "block",
            "blocked_reasons": [{"code": "m3_overclaim", "severity": "major", "message": "Overclaim."}],
        }

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)
    assert report["status"] == "block"
    assert "m3_overclaim" in {r["code"] for r in report["blocked_reasons"]}


def test_cli_writes_report_and_clean_payload(tmp_path: Path) -> None:
    src = tmp_path / "input.json"
    report = tmp_path / "report.json"
    clean = tmp_path / "clean.json"
    src.write_text(json.dumps(_payload("## Result\n\nThis may be limited.")), encoding="utf-8")
    proc = subprocess.run(
        [sys.executable, "-m", "preflight_qa", "check", "--input", str(src), "--out", str(report), "--clean-out", str(clean)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert json.loads(report.read_text())["status"] == "pass"
    assert json.loads(clean.read_text())["markdown"].startswith("## Result")
