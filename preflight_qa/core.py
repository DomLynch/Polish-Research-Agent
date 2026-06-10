from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.error
import urllib.request
from collections.abc import Callable
from typing import Any

Json = dict[str, Any]
Reviewer = Callable[[Json], Json]

DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\])}>,;]+", re.I)
PMID_RE = re.compile(r"\bPMID[:\s#-]*(\d{4,12})\b", re.I)
NUMBER_RE = re.compile(r"(?<![A-Za-z])\d+(?:\.\d+)?%?")
DEBUG_RE = re.compile(
    r"^\s*(TODO|FIXME|DEBUG|TEMPLATE|PLACEHOLDER|INSERT\s+|"
    r"\[to be|lorem ipsum|ignore previous instructions)\b",
    re.I,
)
POS_RE = re.compile(
    r"\b(strong|support(?:s|ed)?|positive|benefit|beneficial|improv(?:e|es|ed)|"
    r"reduc(?:e|es|ed)|increas(?:e|es|ed)|significant|robust)\b",
    re.I,
)
NEGATED_POS_RE = re.compile(
    r"\b(?:not|no|mixed|limited|weak|null|insufficient|inconclusive|unclear)\s+"
    r"(?:strong|support(?:s|ed)?|positive|benefit|beneficial|improv(?:e|es|ed)|"
    r"reduc(?:e|es|ed)|increas(?:e|es|ed)|significant|robust)"
    r"(?:\s+(?:signal|effect|benefit|claim|result|finding|evidence))?\b",
    re.I,
)
WEAK_RE = re.compile(
    r"\b(null|unclear|limited|not significant|non-significant|no effect|"
    r"insufficient|mixed|inconclusive)\b",
    re.I,
)
HEDGE_TERMS = (
    "may", "might", "unclear", "limited", "null", "supported",
    "not supported", "hypothesis", "context", "narrow",
)


def run_preflight(payload: Json, *, use_m3: bool = False, reviewer: Reviewer | None = None) -> Json:
    before = json.loads(json.dumps(payload))
    canonical = _canonical(payload)
    fixes: list[str] = []
    reasons: list[Json] = []

    cleaned = _clean_payload(before, fixes)
    cleaned_canonical = _canonical(cleaned)
    deterministic_reasons = _deterministic_blocks(cleaned_canonical)
    reasons.extend(deterministic_reasons)

    m3_result = {"status": "skipped"}
    if not reasons and (use_m3 or os.getenv("PREFLIGHT_USE_M3", "").lower() in {"1", "true", "yes", "on"}):
        m3_result = reviewer(cleaned_canonical) if reviewer else _minimax_review(cleaned_canonical)
        if m3_result.get("status") == "block":
            reasons.extend(_m3_block_reasons(m3_result))
        elif m3_result.get("status") not in {"pass", "skipped", "not_configured"}:
            reasons.append(_reason("m3_uncertain", "major", "M3 did not return a pass verdict."))

    invariant = _invariant_check(canonical, cleaned_canonical)
    if invariant["status"] != "pass":
        reasons.extend(invariant["failures"])

    status = "block" if reasons else "pass"
    report: Json = {
        "status": status,
        "qa_version": "preflight-v1",
        "input_hash": _hash_json(payload),
        "cleaned_hash": _hash_json(cleaned),
        "safe_fixes_applied": fixes,
        "blocked_reasons": reasons,
        "deterministic_result": {
            "status": "block" if deterministic_reasons else "pass",
            "blocked_reasons": deterministic_reasons,
        },
        "m3_result": m3_result,
        "invariant_result": invariant,
        "cleaned_payload": cleaned if status == "pass" else None,
        "cleaned_body_markdown": _body(cleaned) if status == "pass" else "",
    }
    return report


def _canonical(payload: Json) -> Json:
    body = _body(payload)
    bundle = payload.get("source_bundle") or payload.get("citations") or []
    if not isinstance(bundle, list):
        bundle = []
    evidence_bundle = payload.get("evidence_bundle")
    if not isinstance(evidence_bundle, dict):
        evidence_bundle = {}
    return {
        "artifact_type": str(payload.get("artifact_type") or payload.get("article_type") or ""),
        "title": str(payload.get("title") or ""),
        "abstract": str(payload.get("abstract") or payload.get("summary") or ""),
        "body_markdown": body,
        "source_bundle": [row for row in bundle if isinstance(row, dict)],
        "evidence_bundle": evidence_bundle,
        "metadata": payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {},
    }


def _body(payload: Json) -> str:
    return str(payload.get("body_markdown") or payload.get("markdown") or "")


def _clean_payload(payload: Json, fixes: list[str]) -> Json:
    out = json.loads(json.dumps(payload))
    for key in ("body_markdown", "markdown", "abstract", "summary"):
        if isinstance(out.get(key), str):
            out[key] = _clean_markdown(out[key], fixes)
    sections = out.get("sections")
    if isinstance(sections, dict):
        out["sections"] = {
            k: _clean_markdown(v, fixes) if isinstance(v, str) else v
            for k, v in sections.items()
        }
    return out


def _clean_markdown(text: str, fixes: list[str]) -> str:
    lines = []
    for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if DEBUG_RE.search(line):
            _add_fix(fixes, "strip_template_debug_line")
            continue
        lines.append(line.rstrip())
    paragraphs = "\n".join(lines).split("\n\n")
    deduped: list[str] = []
    last = ""
    for para in paragraphs:
        norm = " ".join(para.split()).lower()
        if norm and norm == last:
            _add_fix(fixes, "remove_duplicate_paragraph")
            continue
        deduped.append(para)
        last = norm
    cleaned = "\n\n".join(deduped)
    repaired = re.sub(r"([a-z\)])\.([A-Z])", r"\1. \2", cleaned)
    if repaired != cleaned:
        _add_fix(fixes, "repair_sentence_spacing")
    return repaired.strip()


def _deterministic_blocks(c: Json) -> list[Json]:
    reasons: list[Json] = []
    body = c["body_markdown"]
    abstract = c["abstract"]
    bundle = c["source_bundle"]
    if not body.strip():
        reasons.append(_reason("missing_body", "critical", "No manuscript markdown was provided."))
    if not bundle:
        reasons.append(_reason("missing_source_bundle", "critical", "No source bundle was provided."))
    reasons.extend(_missing_citations(body + "\n" + abstract, bundle))
    if len(bundle) <= 1 and not WEAK_RE.search(body + " " + abstract):
        reasons.append(_reason(
            "missing_narrow_signal_caveat", "major",
            "Single-source or narrow-signal artifact lacks an explicit limitation/caveat.",
        ))
    prose = (abstract + "\n" + _first_section(body)).lower()
    evidence = _evidence_text(c).lower()
    evidence_without_weak_phrases = WEAK_RE.sub(" ", evidence)
    if _positive_signal(prose) and WEAK_RE.search(evidence) and not _positive_signal(evidence_without_weak_phrases):
        reasons.append(_reason(
            "abstract_results_direction_mismatch", "critical",
            "Prose claims a positive or strong signal while structured evidence is weak/null/unclear.",
        ))
    return reasons


def _missing_citations(text: str, bundle: list[Json]) -> list[Json]:
    dois = {_clean_doi(str(row.get("doi") or "")) for row in bundle}
    pmids = {str(row.get("pmid") or row.get("id") or "") for row in bundle}
    found_dois = {_clean_doi(x) for x in DOI_RE.findall(text)}
    found_pmids = set(PMID_RE.findall(text))
    reasons = [
        _reason("doi_not_in_source_bundle", "critical", f"DOI cited but absent from bundle: {doi}")
        for doi in sorted(found_dois - dois) if doi
    ]
    reasons.extend(
        _reason("pmid_not_in_source_bundle", "critical", f"PMID cited but absent from bundle: {pmid}")
        for pmid in sorted(found_pmids - pmids) if pmid
    )
    return reasons


def _invariant_check(before: Json, after: Json) -> Json:
    failures: list[Json] = []
    checks = (
        ("numbers", _numbers(before), _numbers(after)),
        ("citations", _citations(before), _citations(after)),
        ("hedges", _hedges(before), _hedges(after)),
        ("title", [before["title"]], [after["title"]]),
        ("source_count", [str(len(before["source_bundle"]))], [str(len(after["source_bundle"]))]),
    )
    for code, a, b in checks:
        if a != b:
            failures.append(_reason(f"invariant_{code}_changed", "critical", f"{code} changed during cleaning."))
    return {"status": "block" if failures else "pass", "failures": failures}


def _numbers(c: Json) -> list[str]:
    return NUMBER_RE.findall(c["body_markdown"] + "\n" + c["abstract"])


def _citations(c: Json) -> list[str]:
    text = c["body_markdown"] + "\n" + c["abstract"]
    return sorted({_clean_doi(x) for x in DOI_RE.findall(text)} | {f"pmid:{x}" for x in PMID_RE.findall(text)})


def _hedges(c: Json) -> list[str]:
    text = (c["body_markdown"] + "\n" + c["abstract"]).lower()
    return [term for term in HEDGE_TERMS if re.search(rf"\b{re.escape(term)}\b", text)]


def _evidence_text(c: Json) -> str:
    parts: list[str] = []
    for row in c["source_bundle"]:
        parts.extend(str(row.get(k) or "") for k in (
            "title", "excerpt", "evidence_type", "direction", "support", "relevance",
        ))
    parts.append(json.dumps(c["evidence_bundle"], sort_keys=True))
    return "\n".join(parts)


def _first_section(body: str) -> str:
    return body.split("\n## ", 1)[0][:2000]


def _positive_signal(text: str) -> re.Match[str] | None:
    return POS_RE.search(NEGATED_POS_RE.sub(" ", text))


def _clean_doi(value: str) -> str:
    return value.strip().rstrip(".,;").lower()


def _reason(code: str, severity: str, message: str) -> Json:
    return {"code": code, "severity": severity, "message": message}


def _m3_block_reasons(result: Json) -> list[Json]:
    raw = result.get("blocked_reasons") or []
    items = raw if isinstance(raw, list) else [raw]
    reasons: list[Json] = []
    for item in items:
        if isinstance(item, dict):
            reasons.append(item | {"source": "m3"})
        elif str(item).strip():
            reasons.append(_reason("m3_block", "major", str(item).strip()) | {"source": "m3"})
    if not reasons:
        reasons.append(_reason(
            "m3_block", "major", "M3 returned block without a usable reason.",
        ) | {"source": "m3"})
    return reasons


def _hash_json(payload: Any) -> str:
    return "sha256:" + hashlib.sha256(
        json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _add_fix(fixes: list[str], code: str) -> None:
    if code not in fixes:
        fixes.append(code)


def _minimax_review(c: Json) -> Json:
    api_key = os.getenv("MINIMAX_API_KEY") or os.getenv("ANTHROPIC_API_KEY") or os.getenv("MIMO_API_KEY")
    if not api_key:
        return {"status": "not_configured"}
    base = (
        os.getenv("MINIMAX_BASE_URL")
        or os.getenv("ANTHROPIC_BASE_URL")
        or os.getenv("MIMO_BASE_URL")
        or "https://api.minimax.io/anthropic"
    ).rstrip("/")
    model = os.getenv("MINIMAX_MODEL") or os.getenv("ANTHROPIC_MODEL") or os.getenv("MIMO_MODEL") or "MiniMax-M3"
    prompt = (
        "Return JSON only: {\"status\":\"pass|block\",\"blocked_reasons\":[]}.\n"
        "Block only if prose overclaims, direction conflicts with evidence, or uncertainty should fail closed.\n"
        "You cannot clear deterministic blocks or rewrite text.\n\n"
        + json.dumps({
            "title": c["title"],
            "abstract": c["abstract"][:2000],
            "body_excerpt": c["body_markdown"][:3500],
            "evidence_excerpt": _evidence_text(c)[:3500],
        }, ensure_ascii=False)
    )
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}],
        "temperature": 0,
        "max_tokens": 600,
        "thinking": {"type": "disabled"},
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v1/messages",
        data=body,
        method="POST",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (OSError, urllib.error.HTTPError, ValueError) as exc:
        return {"status": "review_error", "error": type(exc).__name__, "model": model}
    text = _minimax_text(data)
    try:
        out = json.loads(text[text.find("{"): text.rfind("}") + 1])
    except (ValueError, json.JSONDecodeError):
        return {"status": "review_error", "error": "invalid_json", "model": model}
    out["model"] = model
    return out


def _minimax_text(data: Json) -> str:
    content = data.get("content")
    if isinstance(content, list):
        return "\n".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    return str(data.get("text") or data.get("message") or "")
