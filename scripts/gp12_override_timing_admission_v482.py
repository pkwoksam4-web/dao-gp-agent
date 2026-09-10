from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Iterable


def _day(value: object) -> str:
    text = str(value or "").strip()[:10]
    date.fromisoformat(text)
    return text


def _key(row: dict) -> tuple[str, str]:
    symbol = str(row.get("symbol") or "").strip().upper()
    if not symbol:
        raise ValueError(f"missing symbol: {row}")
    return symbol, _day(row.get("ex_date"))


def _ratio(row: dict) -> float:
    value = row.get("corrected_event_ratio")
    if value is None:
        raise ValueError(f"standard override missing corrected_event_ratio: {_key(row)}")
    return float(value)


def merge_standard_overrides(stage_rows: Iterable[Iterable[dict]]) -> list[dict]:
    merged: dict[tuple[str, str], dict] = {}
    for rows in stage_rows:
        for raw in rows:
            row = dict(raw)
            key = _key(row)
            ratio = _ratio(row)
            if key in merged:
                prior = merged[key]
                if abs(_ratio(prior) - ratio) > 1e-12:
                    raise ValueError(f"conflicting standard override ratio: {key}")
                for field in ("announcement_id", "pdf_sha256"):
                    a = str(prior.get(field) or "").strip()
                    b = str(row.get(field) or "").strip()
                    if a and b and a != b:
                        raise ValueError(f"conflicting standard override {field}: {key}")
                    if not a and b:
                        prior[field] = b
                continue
            merged[key] = row
    return [merged[k] for k in sorted(merged)]


def _announcement_date_ms(value: object) -> str:
    if value is None:
        raise ValueError("missing announcementTime")
    dt = datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    return dt.date().isoformat()


def _evidence_fields(record: dict) -> tuple[str, str, str]:
    announcement = record.get("announcement") or {}
    pdf = record.get("pdf_evidence") or {}
    announcement_id = str(announcement.get("announcementId") or "").strip()
    pdf_sha = str(pdf.get("sha256") or "").strip()
    announcement_date = _announcement_date_ms(announcement.get("announcementTime"))
    if not announcement_id or not pdf_sha:
        raise ValueError(f"incomplete standard evidence: {_key(record)}")
    return announcement_id, pdf_sha, announcement_date


def _parse_adjunct_date(url: object) -> str:
    match = re.search(r"finalpage/(\d{4}-\d{2}-\d{2})/", str(url or ""))
    if not match:
        raise ValueError(f"cannot parse adjunct publication date: {url}")
    return _day(match.group(1))


def _iso(value: object) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("missing timestamp")
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


def audit_override_timing(
    standard_overrides: Iterable[dict],
    standard_evidence: Iterable[dict],
    special_overrides: Iterable[dict],
    sameday_proofs: Iterable[dict],
) -> dict:
    standards = list(standard_overrides)
    specials = list(special_overrides)
    evidence_by_key: dict[tuple[str, str], list[dict]] = {}
    for record in standard_evidence:
        evidence_by_key.setdefault(_key(record), []).append(record)

    proof_by_key: dict[tuple[str, str, str], dict] = {}
    for proof in sameday_proofs:
        pkey = (_key(proof)[0], _key(proof)[1], str(proof.get("announcement_id") or "").strip())
        if not pkey[2]:
            raise ValueError(f"same-day proof missing announcement_id: {proof}")
        if pkey in proof_by_key:
            raise ValueError(f"duplicate same-day proof: {pkey}")
        proof_by_key[pkey] = proof

    rows: list[dict] = []
    missing_n = 0
    late_n = 0
    binding_mismatch_n = 0
    missing_preopen_n = 0
    standard_pass_n = 0
    special_pass_n = 0
    same_day_preopen_pass_n = 0

    seen_standard: set[tuple[str, str]] = set()
    for override in standards:
        key = _key(override)
        if key in seen_standard:
            raise ValueError(f"duplicate standard override: {key}")
        seen_standard.add(key)
        candidates = evidence_by_key.get(key, [])
        expected_id = str(override.get("announcement_id") or "").strip()
        expected_sha = str(override.get("pdf_sha256") or "").strip()

        matched: list[tuple[dict, str, str, str]] = []
        for evidence in candidates:
            try:
                ann_id, pdf_sha, ann_date = _evidence_fields(evidence)
            except (ValueError, TypeError, OverflowError):
                continue
            if expected_id and ann_id != expected_id:
                continue
            if expected_sha and pdf_sha != expected_sha:
                continue
            matched.append((evidence, ann_id, pdf_sha, ann_date))

        if len(matched) != 1:
            missing_n += 1
            if candidates:
                binding_mismatch_n += 1
            rows.append({
                "kind": "standard",
                "symbol": key[0],
                "ex_date": key[1],
                "status": "MISSING_OR_AMBIGUOUS_BOUND_EVIDENCE",
                "announcement_id": expected_id,
                "pdf_sha256": expected_sha,
                "publication_date": "",
                "same_day_preopen": "",
            })
            continue

        _, ann_id, pdf_sha, ann_date = matched[0]
        if ann_date > key[1]:
            late_n += 1
            status = "LATE_STANDARD_ANNOUNCEMENT"
        else:
            standard_pass_n += 1
            status = "PASS_STANDARD_OVERRIDE_TIMING"
        rows.append({
            "kind": "standard",
            "symbol": key[0],
            "ex_date": key[1],
            "status": status,
            "announcement_id": ann_id,
            "pdf_sha256": pdf_sha,
            "publication_date": ann_date,
            "same_day_preopen": "",
        })

    seen_special: set[tuple[str, str]] = set()
    for record in specials:
        key = _key(record)
        if key in seen_special:
            raise ValueError(f"duplicate special override: {key}")
        seen_special.add(key)
        provenance = record.get("provenance") or {}
        ann_id = str(provenance.get("announcement_id") or "").strip()
        pdf_sha = str(provenance.get("materialized_sha256") or "").strip()
        if record.get("status") != "PASS_CNINFO_MATERIALIZED" or not ann_id or not pdf_sha:
            missing_n += 1
            rows.append({
                "kind": "special",
                "symbol": key[0],
                "ex_date": key[1],
                "status": "MISSING_SPECIAL_MATERIALIZED_EVIDENCE",
                "announcement_id": ann_id,
                "pdf_sha256": pdf_sha,
                "publication_date": "",
                "same_day_preopen": "",
            })
            continue

        try:
            publication_date = _parse_adjunct_date(provenance.get("adjunct_url"))
        except ValueError:
            missing_n += 1
            rows.append({
                "kind": "special",
                "symbol": key[0],
                "ex_date": key[1],
                "status": "MISSING_SPECIAL_PUBLICATION_DATE",
                "announcement_id": ann_id,
                "pdf_sha256": pdf_sha,
                "publication_date": "",
                "same_day_preopen": "",
            })
            continue

        same_day_preopen: object = ""
        if publication_date > key[1]:
            late_n += 1
            status = "LATE_SPECIAL_ANNOUNCEMENT"
        elif publication_date == key[1]:
            proof = proof_by_key.get((key[0], key[1], ann_id))
            if not proof:
                missing_preopen_n += 1
                status = "MISSING_SAMEDAY_PREOPEN_PROOF"
            else:
                try:
                    ann_time = _iso(proof.get("announcement_time_asia_shanghai"))
                    open_time = _iso(proof.get("ex_date_open_asia_shanghai"))
                    preopen = (
                        proof.get("status") == "PASS"
                        and proof.get("published_before_ex_open") is True
                        and ann_time < open_time
                    )
                except ValueError:
                    preopen = False
                same_day_preopen = preopen
                if preopen:
                    same_day_preopen_pass_n += 1
                    special_pass_n += 1
                    status = "PASS_SPECIAL_SAMEDAY_PREOPEN"
                else:
                    late_n += 1
                    status = "LATE_SPECIAL_SAMEDAY_NOT_PREOPEN"
        else:
            special_pass_n += 1
            status = "PASS_SPECIAL_OVERRIDE_TIMING"

        rows.append({
            "kind": "special",
            "symbol": key[0],
            "ex_date": key[1],
            "status": status,
            "announcement_id": ann_id,
            "pdf_sha256": pdf_sha,
            "publication_date": publication_date,
            "same_day_preopen": same_day_preopen,
        })

    standard_expected_n = len(standards)
    special_expected_n = len(specials)
    total_expected_n = standard_expected_n + special_expected_n
    total_pass_n = standard_pass_n + special_pass_n
    status = (
        "PASS_OVERRIDE_TIMING_ADMISSION"
        if total_expected_n > 0
        and total_pass_n == total_expected_n
        and missing_n == 0
        and late_n == 0
        and missing_preopen_n == 0
        else "REVIEW_OVERRIDE_TIMING_ADMISSION"
    )
    return {
        "status": status,
        "standard_expected_n": standard_expected_n,
        "standard_pass_n": standard_pass_n,
        "special_expected_n": special_expected_n,
        "special_pass_n": special_pass_n,
        "total_expected_n": total_expected_n,
        "total_pass_n": total_pass_n,
        "missing_n": missing_n,
        "binding_mismatch_n": binding_mismatch_n,
        "late_n": late_n,
        "missing_preopen_n": missing_preopen_n,
        "same_day_preopen_pass_n": same_day_preopen_pass_n,
        "rows": rows,
    }


def _load_json(path: str | Path) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _stage_rows(document: dict) -> list[dict]:
    for field in ("event_overrides", "accepted_overrides", "new_overrides"):
        if field in document:
            return list(document.get(field) or [])
    raise ValueError(f"cannot find standard override list in {document.get('artifact')}")


def _write_csv(path: Path, rows: list[dict]) -> None:
    fields = ["kind", "symbol", "ex_date", "status", "announcement_id", "pdf_sha256", "publication_date", "same_day_preopen"]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage-json", action="append", required=True)
    parser.add_argument("--evidence-json", action="append", required=True)
    parser.add_argument("--special-json", required=True)
    parser.add_argument("--sameday-json", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    stage_docs = [_load_json(path) for path in args.stage_json]
    standard_overrides = merge_standard_overrides([_stage_rows(doc) for doc in stage_docs])
    standard_evidence: list[dict] = []
    for path in args.evidence_json:
        standard_evidence.extend(_load_json(path).get("records") or [])
    special_doc = _load_json(args.special_json)
    sameday_doc = _load_json(args.sameday_json)

    result = audit_override_timing(
        standard_overrides,
        standard_evidence,
        special_doc.get("records") or [],
        sameday_doc.get("records") or [],
    )
    result.update({
        "artifact": "GP12_OVERRIDE_TIMING_ADMISSION_V482",
        "version": "V4.82",
        "formal_window": ["2020-06-01", "2026-04-17"],
        "required": {
            "standard_override_n": 270,
            "special_override_n": 11,
            "total_override_n": 281,
            "same_day_special_preopen_n": 2,
        },
        "promotion": {
            "corrected_term_availability_time_verified": result["status"] == "PASS_OVERRIDE_TIMING_ADMISSION",
            "adjusted_close_blocker_closed": False,
            "turnover_ratio_blocker_closed": False,
            "label_provenance_blocker_closed": False,
            "model_freeze_allowed": False,
            "oos_metrics_allowed": False,
        },
    })

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    _write_csv(out_dir / "GP12_OVERRIDE_TIMING_ROWS_V482.csv", result["rows"])
    audit = dict(result)
    audit.pop("rows", None)
    (out_dir / "GP12_OVERRIDE_TIMING_ADMISSION_V482.json").write_text(
        json.dumps(audit, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, ensure_ascii=False, indent=2))

    if not (
        result["status"] == "PASS_OVERRIDE_TIMING_ADMISSION"
        and result["standard_expected_n"] == 270
        and result["standard_pass_n"] == 270
        and result["special_expected_n"] == 11
        and result["special_pass_n"] == 11
        and result["total_pass_n"] == 281
        and result["missing_n"] == 0
        and result["late_n"] == 0
        and result["missing_preopen_n"] == 0
        and result["same_day_preopen_pass_n"] == 2
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
