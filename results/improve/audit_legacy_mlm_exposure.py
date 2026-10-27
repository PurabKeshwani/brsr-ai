"""Attribute the saved legacy MLM corpus to frozen company cohorts.

This is a read-only corpus/DB audit. It does not train, load, or score a model,
and it never reads validation/test labels or computes test performance.
Run once from the repository root with .venv-ml; the output is write-once.
"""

from __future__ import annotations

import csv
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "improve"
OUTPUT = OUT_DIR / "legacy_mlm_exposure.json"
LEDGER = OUT_DIR / "experiment_ledger.csv"
ACCESS_LOG = OUT_DIR / "test_access_log.md"
PHASE0 = OUT_DIR / "phase0_setup.json"
CORPUS = ROOT / "data" / "training" / "mlm_corpus.txt"
DB_DEFAULT = ROOT / "data" / "brsr.db"
COHORT_FILES = {
    "train": ROOT / "data" / "training_company_split" / "train.csv",
    "val": ROOT / "data" / "training_company_split" / "val.csv",
    "test": ROOT / "data" / "training_company_split" / "test.csv",
}
COHORT_BITS = {"train": 1, "val": 2, "test": 4, "outside_split": 8}
MIN_TEXT_LENGTH = 20  # Exact current legacy-builder setting.


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(file_path: Path) -> str:
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def hash_strings(values: set[str]) -> str:
    return sha256_bytes(("\n".join(sorted(values)) + "\n").encode("utf-8"))


def normalize_cin(value: str | None) -> str:
    cin = (value or "").strip().upper()
    if not cin or cin in {"NAN", "NULL", "NONE"}:
        raise ValueError("Encountered blank or invalid CIN in split/DB")
    return cin


def builder_normalize(value: str) -> str:
    text = value.strip().replace("\n", " ").replace("\r", " ")
    return " ".join(text.split())


def git_bytes(*args: str) -> bytes:
    completed = subprocess.run(
        ["git", *args], cwd=ROOT, check=True, capture_output=True
    )
    return completed.stdout


def actual_environment() -> dict:
    diff = git_bytes("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD")
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "git_commit": git_bytes("rev-parse", "HEAD").decode("ascii").strip(),
        "tracked_diff_sha256": sha256_bytes(diff),
        "worktree_dirty": bool(git_bytes("status", "--porcelain")),
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "pandas", "SQLAlchemy")
        },
        "gpu": "NOT USED: no model load or training",
    }


def database_path() -> Path:
    url = os.environ.get("BRSR_DB_URL")
    if not url:
        return DB_DEFAULT
    if not url.startswith("sqlite:///"):
        raise ValueError("BRSR_DB_URL is not SQLite; audit needs an explicit DB adapter")
    raw = url[len("sqlite:///") :]
    if os.name == "nt" and len(raw) > 2 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]
    path = Path(raw)
    return path if path.is_absolute() else ROOT / path


def append_ledger(run_id: str, status: str, result: str) -> None:
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(
            [
                run_id,
                "Audit saved legacy MLM corpus exposure before leakage-control decision",
                "audit_legacy_mlm_exposure.py",
                "NOT RUN",
                "NOT RUN",
                result,
                status,
                OUTPUT.relative_to(ROOT).as_posix(),
            ]
        )


def append_access(run_id: str, status: str, note: str) -> None:
    with ACCESS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| {run_id} | {now()} | {status} | "
            "`data/training_company_split/test.csv` | "
            f"`{OUTPUT.relative_to(ROOT).as_posix()}` | "
            f"{note} |\n"
        )


def read_split_cins(phase0: dict) -> tuple[dict[str, set[str]], dict]:
    cohorts: dict[str, set[str]] = {}
    details = {}
    for name, file_path in COHORT_FILES.items():
        actual_hash = sha256_file(file_path)
        expected_hash = phase0["dataset_metadata"][name]["sha256"]
        if actual_hash != expected_hash:
            raise ValueError(f"Frozen {name} CSV hash changed")
        cins: set[str] = set()
        rows = 0
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "cin" not in reader.fieldnames:
                raise ValueError(f"Missing cin column in {name} CSV")
            for row in reader:
                cins.add(normalize_cin(row["cin"]))
                rows += 1
        if rows != phase0["dataset_metadata"][name]["rows"]:
            raise ValueError(f"Frozen {name} row count changed")
        if len(cins) != phase0["dataset_metadata"][name]["unique_cins"]:
            raise ValueError(f"Frozen {name} CIN count changed")
        cohorts[name] = cins
        details[name] = {
            "rows": rows,
            "unique_cins": len(cins),
            "csv_sha256": actual_hash,
            "cin_set_sha256": hash_strings(cins),
        }
    if any(cohorts[a] & cohorts[b] for a, b in (("train", "val"), ("train", "test"), ("val", "test"))):
        raise ValueError("Frozen cohorts have CIN overlap")
    return cohorts, details


def audit() -> dict:
    phase0 = json.loads(PHASE0.read_text(encoding="utf-8"))
    if phase0.get("status") != "PASS":
        raise ValueError("Phase 0 setup is not PASS")
    if not CORPUS.is_file():
        raise FileNotFoundError(CORPUS)

    corpus_bytes = CORPUS.read_bytes()
    corpus_lines = corpus_bytes.decode("utf-8").splitlines()
    if any(not line for line in corpus_lines):
        raise ValueError("Saved corpus contains blank lines")
    if len(corpus_lines) != len(set(corpus_lines)):
        raise ValueError("Saved corpus contains duplicate lines")
    corpus = set(corpus_lines)
    corpus_sha = sha256_bytes(corpus_bytes)
    corpus_stat = CORPUS.stat()

    append_access(
        RUN_ID,
        "METADATA_ONLY_STARTED",
        "CIN membership plus saved-corpus attribution; no labels/predictions",
    )
    cohorts, split_details = read_split_cins(phase0)
    bit_by_cin = {cin: COHORT_BITS[name] for name in ("train", "val", "test") for cin in cohorts[name]}

    db_path = database_path().resolve()
    if not db_path.is_file():
        raise FileNotFoundError(db_path)
    db_before = db_path.stat()
    masks = dict.fromkeys(corpus, 0)
    current_db_texts: set[str] = set()
    fact_rows_by_cohort: Counter[str] = Counter()
    matched_fact_rows_by_cohort: Counter[str] = Counter()
    matched_cins_by_cohort: dict[str, set[str]] = {name: set() for name in COHORT_BITS}
    valid_fact_rows = 0
    conn = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    try:
        conn.execute("PRAGMA query_only = ON")
        query = """
            SELECT companies.cin, facts.value
            FROM facts
            JOIN filings ON facts.filing_id = filings.id
            JOIN companies ON filings.company_id = companies.id
            WHERE facts.concept LIKE '%ExplanatoryTextBlock%'
        """
        for raw_cin, raw_value in conn.execute(query):
            if raw_value is None:
                continue
            normalized = builder_normalize(raw_value)
            if len(normalized) < MIN_TEXT_LENGTH:
                continue
            valid_fact_rows += 1
            current_db_texts.add(normalized)
            cin = normalize_cin(raw_cin)
            bit = bit_by_cin.get(cin, COHORT_BITS["outside_split"])
            cohort = next(name for name, candidate in COHORT_BITS.items() if candidate == bit)
            fact_rows_by_cohort[cohort] += 1
            if normalized in masks:
                masks[normalized] |= bit
                matched_fact_rows_by_cohort[cohort] += 1
                matched_cins_by_cohort[cohort].add(cin)
    finally:
        conn.close()
    db_after = db_path.stat()
    if (db_before.st_size, db_before.st_mtime_ns) != (db_after.st_size, db_after.st_mtime_ns):
        raise RuntimeError("Database changed while counting; result is not a stable snapshot")
    if sha256_file(CORPUS) != corpus_sha:
        raise RuntimeError("Saved corpus changed while counting")
    for name, file_path in COHORT_FILES.items():
        if sha256_file(file_path) != split_details[name]["csv_sha256"]:
            raise RuntimeError(f"Frozen {name} CSV changed while counting")

    mask_counts = Counter(masks.values())
    matched = sum(count for mask, count in mask_counts.items() if mask)
    unmatched = mask_counts[0]
    db_only = len(current_db_texts - corpus)
    any_val = sum(count for mask, count in mask_counts.items() if mask & 2)
    any_test = sum(count for mask, count in mask_counts.items() if mask & 4)
    val_test_union = sum(count for mask, count in mask_counts.items() if mask & 6)
    val_test_without_train = sum(count for mask, count in mask_counts.items() if (mask & 6) and not (mask & 1))
    val_test_shared_with_train = sum(count for mask, count in mask_counts.items() if (mask & 6) and (mask & 1))
    reconstructed = unmatched == 0 and db_only == 0

    checkpoint_config = ROOT / "data" / "models" / "domain_adapted_bert" / "final_model" / "config.json"
    checkpoint = {
        "path": str(checkpoint_config.relative_to(ROOT)),
        "config_exists": checkpoint_config.is_file(),
        "config_mtime_utc": datetime.fromtimestamp(checkpoint_config.stat().st_mtime, timezone.utc).isoformat()
        if checkpoint_config.is_file() else None,
        "exact_corpus_to_checkpoint_link": "UNVERIFIED: config does not record corpus hash",
    }
    evidence = (
        "VAL_TEST_ASSOCIATED_SENTENCES_FOUND"
        if val_test_union
        else "NO_ASSOCIATED_SENTENCES_IN_CURRENT_DB_BUT_HISTORICAL_LINK_UNVERIFIED"
    )
    return {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "PHASE_1_LEGACY_MLM_EXPOSURE_AUDIT",
        "status": "PASS",
        "count_role": "Historical saved corpus attribution using current DB; not model inference",
        "decision_rule_frozen_in": "results/improve/prereg.md",
        "evidence_status": evidence,
        "decision": "TRAIN_COMPANY_ONLY_MLM_REQUIRED_AS_LEAKAGE_CONTROL"
        if val_test_union or not reconstructed or checkpoint["exact_corpus_to_checkpoint_link"].startswith("UNVERIFIED")
        else "LEGACY_MLM_CAN_BE_RETAINED",
        "decision_verdict_type": "LEAKAGE CONTROL; not an accuracy improvement",
        "new_training": "NOT RUN",
        "new_inference": "NOT RUN",
        "new_test_performance": "NOT RUN",
        "historical_checkpoint": checkpoint,
        "saved_corpus": {
            "path": str(CORPUS.relative_to(ROOT)),
            "sha256": corpus_sha,
            "mtime_utc": datetime.fromtimestamp(corpus_stat.st_mtime, timezone.utc).isoformat(),
            "bytes": len(corpus_bytes),
            "unique_sentences": len(corpus),
            "minimum_length": MIN_TEXT_LENGTH,
            "attribution_denominator": "All unique saved corpus sentences",
        },
        "attribution": {
            "matched_unique_sentences_in_current_db": matched,
            "unmatched_saved_sentences": unmatched,
            "current_db_valid_unique_sentences_not_in_saved_corpus": db_only,
            "entire_saved_corpus_reconstructed_from_current_db": reconstructed,
            "any_validation_cin_sentences": any_val,
            "any_test_cin_sentences": any_test,
            "validation_or_test_union_sentences": val_test_union,
            "validation_or_test_union_percent_of_saved_corpus": 100 * val_test_union / len(corpus) if corpus else None,
            "validation_or_test_without_train_sentences": val_test_without_train,
            "validation_or_test_shared_with_train_sentences": val_test_shared_with_train,
            "unmatched_percent_of_saved_corpus": 100 * unmatched / len(corpus) if corpus else None,
            "source_masks": {
                "+".join(name for name, bit in COHORT_BITS.items() if mask & bit) if mask else "unmatched": count
                for mask, count in sorted(mask_counts.items())
            },
            "current_db_valid_fact_rows": valid_fact_rows,
            "current_db_valid_unique_sentences": len(current_db_texts),
            "current_db_valid_fact_rows_by_cohort": dict(fact_rows_by_cohort),
            "saved_corpus_matched_fact_rows_by_cohort": dict(matched_fact_rows_by_cohort),
            "saved_corpus_matched_unique_cins_by_cohort": {
                name: len(cins) for name, cins in matched_cins_by_cohort.items()
            },
        },
        "split_metadata": split_details,
        "database": {
            "path": str(db_path),
            "bytes": db_before.st_size,
            "mtime_utc": datetime.fromtimestamp(db_before.st_mtime, timezone.utc).isoformat(),
            "query": "Fact.concept LIKE '%ExplanatoryTextBlock%' joined to Filing and Company",
        },
        "method_limit": (
            "Saved corpus has no CIN; shared text is counted in every contributing cohort. "
            "Current DB may differ from the historical ingestion snapshot. "
            "A corpus/config timestamp is not cryptographic proof of the checkpoint's training input."
        ),
        "environment": actual_environment(),
        "script_sha256": sha256_file(Path(__file__)),
        "prereg_sha256": sha256_file(OUT_DIR / "prereg.md"),
        "phase0_run_id": phase0["run_id"],
        "finished_at_utc": now(),
    }


RUN_ID = "P1-MLM-AUDIT-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def main() -> None:
    global OUTPUT
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default="legacy_mlm_exposure.json",
        help="New JSON filename inside results/improve (for a separately logged retry)",
    )
    args = parser.parse_args()
    OUTPUT = (OUT_DIR / args.output).resolve()
    if OUTPUT.parent != OUT_DIR.resolve() or OUTPUT.suffix.lower() != ".json":
        raise ValueError("--output must be a JSON filename inside results/improve")
    if OUTPUT.exists():
        raise FileExistsError(f"Refusing to overwrite {OUTPUT}")
    append_ledger(RUN_ID, "RUNNING", "RUNNING")
    result: dict
    try:
        result = audit()
    except Exception as exc:
        result = {
            "schema_version": 1,
            "run_id": RUN_ID,
            "phase": "PHASE_1_LEGACY_MLM_EXPOSURE_AUDIT",
            "status": "FAIL",
            "error_type": type(exc).__name__,
            "error": str(exc),
            "new_training": "NOT RUN",
            "new_inference": "NOT RUN",
            "new_test_performance": "NOT RUN",
            "finished_at_utc": now(),
        }
    with OUTPUT.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    if result["status"] == "PASS":
        append_access(RUN_ID, "METADATA_ONLY_PASS", "Corpus/DB attribution only; no test labels or metrics")
        append_ledger(RUN_ID, "PASS", result["decision_verdict_type"])
        a = result["attribution"]
        print(f"Legacy MLM exposure audit: PASS; saved unique sentences={result['saved_corpus']['unique_sentences']}")
        print(f"Current-DB matched={a['matched_unique_sentences_in_current_db']}; unmatched={a['unmatched_saved_sentences']}; DB-only={a['current_db_valid_unique_sentences_not_in_saved_corpus']}")
        print(f"Val-associated={a['any_validation_cin_sentences']}; test-associated={a['any_test_cin_sentences']}; union={a['validation_or_test_union_sentences']} ({a['validation_or_test_union_percent_of_saved_corpus']:.2f}% of saved corpus)")
        print(f"Union without train={a['validation_or_test_without_train_sentences']}; shared with train={a['validation_or_test_shared_with_train_sentences']}")
        print(f"Decision: {result['decision']} ({result['decision_verdict_type']})")
    else:
        append_access(RUN_ID, "METADATA_ONLY_FAIL", "Audit failed; see result JSON")
        append_ledger(RUN_ID, "FAIL", result["error_type"])
        print(f"Legacy MLM exposure audit: FAIL — {result['error_type']}: {result['error']}")
    print(f"Results: {OUTPUT}")
    print("Training/inference/test performance: NOT RUN")


if __name__ == "__main__":
    main()
