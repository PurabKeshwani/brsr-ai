"""Audit the legacy Stage 5 100-company sample against Stage 3 splits.

This script only materializes and audits the old validation sample. It does
not load a model or calculate performance metrics. Run from repo root with
the project's .venv-ml Python.
"""
from __future__ import annotations

import hashlib
import json
import sys
import unicodedata
from pathlib import Path

import pandas as pd

BASE = Path(__file__).resolve().parents[2]
SRC = BASE / "src"
sys.path.insert(0, str(SRC))

SPLIT_DIR = BASE / "data/training_company_split"
OUT_JSON = BASE / "results/audit/stage5_original_393_overlap.json"
OUT_SAMPLE = BASE / "data/validation/stage5_original_100_company_sample.csv"
PRINCIPLE_TO_LABEL = {f"Principle{i}Member": i for i in range(1, 10)}
EXPECTED_ROWS = 393
EXPECTED_COMPANIES = 100


def normalized_hash(text: object) -> str:
    normalized = " ".join(unicodedata.normalize("NFKC", str(text or "")).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def load_stage3_splits() -> dict[str, pd.DataFrame]:
    splits = {}
    for name in ("train", "val", "test"):
        path = SPLIT_DIR / f"{name}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing Stage 3 company split: {path}")
        df = pd.read_csv(path, dtype={"cin": "string"})
        required = {"text", "cin", "principle_id"}
        if not required.issubset(df.columns):
            raise ValueError(f"{path} missing required columns: {sorted(required - set(df.columns))}")
        df["cin_norm"] = df["cin"].fillna("").astype(str).str.strip().str.upper()
        df["text_hash"] = df["text"].map(normalized_hash)
        splits[name] = df
    return splits


def materialize_legacy_sample() -> pd.DataFrame:
    from db.models import Company, Fact, Filing
    from db.session import get_session, init_db

    init_db()
    rows: list[dict] = []
    with get_session() as session:
        # The old validator selected the first 100 companies with LIMIT 100
        # and no explicit order. Use primary-key order for a reproducible
        # reconstruction and disclose this ordering assumption in the output.
        companies = session.query(Company).order_by(Company.id).limit(EXPECTED_COMPANIES).all()
        if len(companies) != EXPECTED_COMPANIES:
            raise ValueError(f"Expected at least 100 companies in DB; found {len(companies)}")

        for company in companies:
            filing = (
                session.query(Filing)
                .filter_by(company_id=company.id)
                .order_by(Filing.financial_year_end.desc())
                .first()
            )
            if filing is None:
                continue
            facts = (
                session.query(Fact)
                .filter(Fact.filing_id == filing.id, Fact.concept.like("%ExplanatoryTextBlock%"))
                .all()
            )
            text_to_principles: dict[str, set[int]] = {}
            for fact in facts:
                principle_dim = (fact.dimensions or {}).get("PrincipleAxis")
                text = (fact.value or "").strip()
                if principle_dim in PRINCIPLE_TO_LABEL and len(text) >= 20:
                    text_to_principles.setdefault(text, set()).add(PRINCIPLE_TO_LABEL[principle_dim])

            for text, principles in text_to_principles.items():
                if len(principles) != 1 or text.lower().startswith(("http://", "https://")):
                    continue
                principle = next(iter(principles))
                rows.append({
                    "cin": company.cin,
                    "company_name": company.name,
                    "filing_id": filing.id,
                    "financial_year_end": filing.financial_year_end,
                    "true_principle": principle,
                    "text": text,
                })

    sample = pd.DataFrame(rows)
    if sample.empty:
        raise ValueError("Legacy Stage 5 sample reconstruction returned no rows.")
    sample["cin_norm"] = sample["cin"].fillna("").astype(str).str.strip().str.upper()
    sample["text_hash"] = sample["text"].map(normalized_hash)
    return sample


def main() -> None:
    splits = load_stage3_splits()
    sample = materialize_legacy_sample()
    sample_cins = set(sample["cin_norm"])
    sample_hashes = set(sample["text_hash"])

    overlap = {}
    for name, split in splits.items():
        split_cins = set(split["cin_norm"])
        split_hashes = set(split["text_hash"])
        company_cins = sample_cins & split_cins
        text_hashes = sample_hashes & split_hashes
        sample_rows_by_company = int(sample["cin_norm"].isin(company_cins).sum())
        sample_rows_by_hash = int(sample["text_hash"].isin(text_hashes).sum())
        overlap[name] = {
            "split_rows": int(len(split)),
            "split_companies": int(split["cin_norm"].nunique()),
            "overlap_cin_count": len(company_cins),
            "overlap_sample_companies": sorted(company_cins),
            "overlap_sample_rows_by_cin": sample_rows_by_company,
            "overlap_unique_normalized_text_hash_count": len(text_hashes),
            "overlap_sample_rows_by_text_hash": sample_rows_by_hash,
            "overlap_hashes_shared_across_different_cins": int(
                sum(
                    1 for _, row in sample[sample["text_hash"].isin(text_hashes)].iterrows()
                    if not ((split.loc[split["text_hash"] == row["text_hash"], "cin_norm"] == row["cin_norm"]).any())
                )
            ),
        }

    report = {
        "audit": "Stage 5 legacy 100-company sample overlap with Stage 3 company-disjoint splits",
        "reconstruction": "latest filing per first 100 companies ordered by Company.id; old validator used LIMIT 100 without explicit ordering",
        "expected_legacy_n": EXPECTED_ROWS,
        "reconstructed_n": int(len(sample)),
        "expected_legacy_companies": EXPECTED_COMPANIES,
        "reconstructed_companies": int(sample["cin_norm"].nunique()),
        "sample_size_matches_reported": len(sample) == EXPECTED_ROWS,
        "companies_count_matches_reported": sample["cin_norm"].nunique() == EXPECTED_COMPANIES,
        "text_hash_normalization": "Unicode NFKC, casefold, collapse whitespace, SHA-256",
        "split_overlap": overlap,
        "model_path_configured_in_compliance_mapper": "data/models/brsr_principle_classifier/final_model_unweighted_93.68",
        "company_disjoint_stage3_seed99_checkpoint": "data/models/brsr_company_split_classifier/seed_99/best_model",
        "warning": "Current compliance mapper supervised path is not the Stage 3 company-disjoint seed_99 checkpoint. Do not attribute legacy metrics to the company-disjoint Stage 3 model without a fresh evaluation.",
        "artifacts": {
            "reconstructed_sample_csv": str(OUT_SAMPLE.relative_to(BASE)),
            "overlap_report_json": str(OUT_JSON.relative_to(BASE)),
        },
    }
    OUT_SAMPLE.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    sample.drop(columns=["cin_norm", "text_hash"]).to_csv(OUT_SAMPLE, index=False, encoding="utf-8-sig")
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print("Stage 5 overlap audit (no model inference)")
    print(f"Reconstructed sample: N={len(sample)}, companies={sample['cin_norm'].nunique()} (reported N=393, companies=100)")
    print(f"Matches reported size: {report['sample_size_matches_reported']}; company count matches: {report['companies_count_matches_reported']}")
    for name, item in overlap.items():
        print(
            f"{name}: CIN overlap={item['overlap_cin_count']} companies / "
            f"{item['overlap_sample_rows_by_cin']} sample rows; exact normalized text-hash overlap="
            f"{item['overlap_unique_normalized_text_hash_count']} hashes / "
            f"{item['overlap_sample_rows_by_text_hash']} sample rows"
        )
    print("Configured supervised model: data/models/brsr_principle_classifier/final_model_unweighted_93.68")
    print("Stage 3 company-disjoint seed_99 checkpoint: data/models/brsr_company_split_classifier/seed_99/best_model")
    print(f"Sample CSV: {OUT_SAMPLE}")
    print(f"JSON report: {OUT_JSON}")


if __name__ == "__main__":
    main()
