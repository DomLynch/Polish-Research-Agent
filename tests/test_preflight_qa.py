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


def test_negated_support_over_null_evidence_does_not_block_direction() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe primary claim is not supported; evidence remains limited.",
        abstract="The results show mixed support, not significant benefit.",
        sources=[
            {"title": "Null trial", "doi": "10.1000/abc", "excerpt": "no effect and not significant"},
            {"title": "Limited trial", "doi": "10.1000/def", "excerpt": "limited signal"},
        ],
    ))
    assert report["status"] == "pass"
    assert "abstract_results_direction_mismatch" not in {r["code"] for r in report["blocked_reasons"]}


def test_m3_can_add_block_but_not_needed_for_pass() -> None:
    def reviewer(_payload: dict) -> dict:
        return {
            "status": "block",
            "blocked_reasons": [{"code": "m3_overclaim", "severity": "major", "message": "Overclaim."}],
        }

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)
    assert report["status"] == "block"
    assert "m3_overclaim" in {r["code"] for r in report["blocked_reasons"]}


def test_m3_string_block_reason_fails_closed() -> None:
    def reviewer(_payload: dict) -> dict:
        return {
            "status": "block",
            "blocked_reasons": ["overclaim: cures Alzheimer's in humans"],
        }

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)

    assert report["status"] == "block"
    assert report["blocked_reasons"] == [{
        "code": "m3_block",
        "severity": "major",
        "message": "overclaim: cures Alzheimer's in humans",
        "source": "m3",
    }]


def test_m3_block_without_reasons_fails_closed() -> None:
    def reviewer(_payload: dict) -> dict:
        return {"status": "block", "blocked_reasons": []}

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)

    assert report["status"] == "block"
    assert report["blocked_reasons"][0]["code"] == "m3_block"
    assert report["blocked_reasons"][0]["source"] == "m3"


def test_m3_required_but_not_configured_fails_closed() -> None:
    def reviewer(_payload: dict) -> dict:
        return {"status": "not_configured"}

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)

    assert report["status"] == "block"
    assert {r["code"] for r in report["blocked_reasons"]} == {"m3_not_configured"}


def test_duplicate_paragraph_with_number_is_cleaned_without_blocking() -> None:
    body = "## Result\n\nEffect was 5% lower.\n\nEffect was 5% lower."
    report = run_preflight(_payload(body))
    assert report["status"] == "pass"
    assert report["safe_fixes_applied"] == ["remove_duplicate_paragraph"]
    assert report["invariant_result"]["status"] == "pass"
    assert report["cleaned_body_markdown"].count("Effect was 5% lower.") == 1


def test_overclaim_without_structured_evidence_blocks() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe treatment shows strong significant benefit and improves outcomes.",
        abstract="Strong positive benefit demonstrated.",
        sources=[{"doi": "10.1000/abc"}, {"doi": "10.1000/def"}],
    ))
    assert report["status"] == "block"
    assert "overclaim_ungated" in {r["code"] for r in report["blocked_reasons"]}


def test_overclaim_not_flagged_when_structured_evidence_present() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe treatment shows strong significant benefit and improves outcomes.",
        abstract="Strong positive benefit demonstrated.",
        sources=[
            {"title": "Trial", "doi": "10.1000/abc", "excerpt": "significant benefit", "direction": "positive"},
            {"title": "Trial2", "doi": "10.1000/def", "excerpt": "improved outcomes", "direction": "positive"},
        ],
    ))
    assert "overclaim_ungated" not in {r["code"] for r in report["blocked_reasons"]}


def test_env_only_m3_not_configured_fails_closed(monkeypatch) -> None:
    monkeypatch.setenv("PREFLIGHT_USE_M3", "1")

    def reviewer(_payload: dict) -> dict:
        return {"status": "not_configured"}

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=False, reviewer=reviewer)

    assert report["status"] == "block"
    assert {r["code"] for r in report["blocked_reasons"]} == {"m3_not_configured"}


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
