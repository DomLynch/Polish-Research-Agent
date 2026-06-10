from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.request
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


def _advisory_codes(report: dict) -> set[str]:
    return {a["code"] for a in report["advisories"]}


def test_duplicate_paragraph_is_cleaned_without_blocking() -> None:
    body = "## Result\n\nThis may be limited.\n\nThis may be limited."
    report = run_preflight(_payload(body))
    assert report["status"] == "pass"
    assert report["safe_fixes_applied"] == ["remove_duplicate_paragraph"]
    assert report["cleaned_body_markdown"].count("This may be limited.") == 1


def test_duplicate_paragraph_with_number_is_cleaned_without_blocking() -> None:
    body = "## Result\n\nEffect was 5% lower.\n\nEffect was 5% lower."
    report = run_preflight(_payload(body))
    assert report["status"] == "pass"
    assert report["safe_fixes_applied"] == ["remove_duplicate_paragraph"]
    assert report["invariant_result"]["status"] == "pass"
    assert report["cleaned_body_markdown"].count("Effect was 5% lower.") == 1


def test_missing_doi_is_advisory_only() -> None:
    report = run_preflight(_payload("This may cite DOI 10.9999/missing."))
    assert report["status"] == "pass"
    assert report["blocked_reasons"] == []
    assert "doi_not_in_source_bundle" in _advisory_codes(report)
    assert report["cleaned_payload"] is not None


def test_positive_abstract_over_null_evidence_is_advisory_not_block() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe claim is supported.",
        abstract="The evidence shows strong positive benefit.",
        sources=[{"title": "Null trial", "excerpt": "no effect and not significant"}],
    ))
    assert report["status"] == "pass"
    assert report["blocked_reasons"] == []
    assert "abstract_results_direction_mismatch" in _advisory_codes(report)


def test_negated_support_over_null_evidence_has_no_direction_advisory() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe primary claim is not supported; evidence remains limited.",
        abstract="The results show mixed support, not significant benefit.",
        sources=[
            {"title": "Null trial", "doi": "10.1000/abc", "excerpt": "no effect and not significant"},
            {"title": "Limited trial", "doi": "10.1000/def", "excerpt": "limited signal"},
        ],
    ))
    assert report["status"] == "pass"
    assert "abstract_results_direction_mismatch" not in _advisory_codes(report)


def test_overclaim_without_structured_evidence_is_advisory() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe treatment shows strong significant benefit and improves outcomes.",
        abstract="Strong positive benefit demonstrated.",
        sources=[{"doi": "10.1000/abc"}, {"doi": "10.1000/def"}],
    ))
    assert report["status"] == "pass"
    assert "overclaim_ungated" in _advisory_codes(report)


def test_overclaim_not_flagged_when_structured_evidence_present() -> None:
    report = run_preflight(_payload(
        "## Result\n\nThe treatment shows strong significant benefit and improves outcomes.",
        abstract="Strong positive benefit demonstrated.",
        sources=[
            {"title": "Trial", "doi": "10.1000/abc", "excerpt": "significant benefit", "direction": "positive"},
            {"title": "Trial2", "doi": "10.1000/def", "excerpt": "improved outcomes", "direction": "positive"},
        ],
    ))
    assert "overclaim_ungated" not in _advisory_codes(report)


def test_m3_block_verdict_is_advisory_only() -> None:
    def reviewer(_payload: dict) -> dict:
        return {
            "status": "block",
            "blocked_reasons": [{"code": "m3_overclaim", "severity": "major", "message": "Overclaim."}],
        }

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)
    assert report["status"] == "pass"
    assert report["blocked_reasons"] == []
    assert "m3_overclaim" in _advisory_codes(report)


def test_m3_string_block_reason_is_recorded_advisory() -> None:
    def reviewer(_payload: dict) -> dict:
        return {
            "status": "block",
            "blocked_reasons": ["overclaim: cures Alzheimer's in humans"],
        }

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)

    assert report["status"] == "pass"
    assert report["advisories"] == [{
        "code": "m3_block",
        "severity": "major",
        "message": "overclaim: cures Alzheimer's in humans",
        "source": "m3",
    }]


def test_m3_block_without_reasons_records_advisory() -> None:
    def reviewer(_payload: dict) -> dict:
        return {"status": "block", "blocked_reasons": []}

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)

    assert report["status"] == "pass"
    assert report["advisories"][0]["code"] == "m3_block"
    assert report["advisories"][0]["source"] == "m3"


def test_m3_not_configured_is_advisory() -> None:
    def reviewer(_payload: dict) -> dict:
        return {"status": "not_configured"}

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True, reviewer=reviewer)

    assert report["status"] == "pass"
    assert "m3_not_configured" in _advisory_codes(report)


def test_env_only_m3_not_configured_is_advisory(monkeypatch) -> None:
    monkeypatch.setenv("PREFLIGHT_USE_M3", "1")

    def reviewer(_payload: dict) -> dict:
        return {"status": "not_configured"}

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=False, reviewer=reviewer)

    assert report["status"] == "pass"
    assert "m3_not_configured" in _advisory_codes(report)


def test_env_only_m3_without_key_uses_real_not_configured_path(monkeypatch) -> None:
    monkeypatch.setenv("PREFLIGHT_USE_M3", "1")
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MIMO_API_KEY", raising=False)

    report = run_preflight(_payload("## Result\n\nThis may be limited."))

    assert report["status"] == "pass"
    assert report["m3_result"]["status"] == "not_configured"
    assert "m3_not_configured" in _advisory_codes(report)


def test_cli_use_m3_without_key_records_not_configured_advisory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("MINIMAX_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("MIMO_API_KEY", raising=False)
    src = tmp_path / "input.json"
    report = tmp_path / "report.json"
    src.write_text(json.dumps(_payload("## Result\n\nThis may be limited.")), encoding="utf-8")
    env = os.environ.copy()
    for name in ("MINIMAX_API_KEY", "ANTHROPIC_API_KEY", "MIMO_API_KEY", "PREFLIGHT_USE_M3"):
        env.pop(name, None)

    proc = subprocess.run(
        [sys.executable, "-m", "preflight_qa", "check", "--use-m3", "--input", str(src), "--out", str(report)],
        cwd=Path(__file__).resolve().parents[1],
        text=True,
        capture_output=True,
        check=False,
        env=env,
    )

    data = json.loads(report.read_text())
    assert proc.returncode == 0, proc.stderr
    assert data["status"] == "pass"
    assert data["m3_result"]["status"] == "not_configured"
    assert "m3_not_configured" in {row["code"] for row in data["advisories"]}


def test_minimax_is_default_advisory_reviewer_model(monkeypatch) -> None:
    class FakeResponse:
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps({
                "content": [{"text": "{\"status\":\"pass\",\"blocked_reasons\":[]}"}],
            }).encode("utf-8")

    requests = []

    def fake_urlopen(req: urllib.request.Request, timeout: int) -> FakeResponse:
        requests.append((req, timeout))
        return FakeResponse()

    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    monkeypatch.delenv("MINIMAX_MODEL", raising=False)
    monkeypatch.delenv("ANTHROPIC_MODEL", raising=False)
    monkeypatch.delenv("MIMO_MODEL", raising=False)
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)

    report = run_preflight(_payload("## Result\n\nThis may be limited."), use_m3=True)

    assert report["status"] == "pass"
    assert report["m3_result"]["model"] == "MiniMax-M3"
    assert report["m3_result"]["status"] == "pass"
    assert report["advisories"] == []
    assert requests


def test_cleaning_reverts_to_original_when_invariant_trips() -> None:
    body = "## Result\n\nTODO drop 5% placeholder\n\nThis may be limited."
    report = run_preflight(_payload(body))
    assert report["status"] == "pass"
    assert report["safe_fixes_applied"] == []
    assert "TODO drop 5% placeholder" in report["cleaned_body_markdown"]
    assert "cleaning_reverted" in _advisory_codes(report)


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
