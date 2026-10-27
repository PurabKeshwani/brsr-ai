"""Build a frozen train-company-only MLM corpus from the saved legacy corpus.

Text selection is preregistered in results/improve/prereg.md: retain an old
corpus sentence only if the current DB attributes it exclusively to a train
CIN. Exact text also filed by validation/test companies is embargoed. This
script never reads principle labels or performance metrics and never trains.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import platform
import sqlite3
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
IMPROVE = ROOT / "results" / "improve"
CORPUS_IN = ROOT / "data" / "training" / "mlm_corpus.txt"
CORPUS_OUT = ROOT / "data" / "training" / "mlm_corpus_train_only_v1.txt"
MANIFEST = IMPROVE / "train_only_mlm_corpus_manifest.json"
AUDIT_PATH = IMPROVE / "legacy_mlm_exposure.json"
PHASE0_PATH = IMPROVE / "phase0_setup.json"
LEDGER = IMPROVE / "experiment_ledger.csv"
ACCESS_LOG = IMPROVE / "test_access_log.md"
BITS = {"train": 1, "val": 2, "test": 4, "outside_split": 8}
RUN_ID = "P1-MLM-CORPUS-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(file_path: Path) -> str:
    h = hashlib.sha256()
    with file_path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def normalize_text(value: str) -> str:
    text = value.strip().replace("\n", " ").replace("\r", " ")
    return " ".join(text.split())


def normalize_cin(value: str | None) -> str:
    cin = (value or "").strip().upper()
    if not cin or cin in {"NAN", "NONE", "NULL"}:
        raise ValueError("Blank/invalid CIN encountered")
    return cin


def cin_digest(cins: set[str]) -> str:
    return digest(("\n".join(sorted(cins)) + "\n").encode("utf-8"))


def git_output(*args: str) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=True).stdout


def environment() -> dict:
    diff = git_output("diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD")
    return {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "git_commit": git_output("rev-parse", "HEAD").decode("ascii").strip(),
        "tracked_diff_sha256": digest(diff),
        "worktree_dirty": bool(git_output("status", "--porcelain")),
        "package_versions": {
            name: importlib.metadata.version(name)
            for name in ("torch", "transformers", "pandas", "SQLAlchemy")
        },
        "gpu": "NOT USED: no model load or training",
    }


def ledger(status: str, verdict: str, result_path: Path) -> None:
    with LEDGER.open("a", encoding="utf-8", newline="") as handle:
        csv.writer(handle).writerow(
            [
                RUN_ID,
                "Remove validation/test company text from MLM adaptation",
                "build_train_only_mlm_corpus.py; mask=train only",
                "NOT RUN",
                "NOT RUN",
                verdict,
                status,
                result_path.relative_to(ROOT).as_posix(),
            ]
        )


def access(status: str, note: str) -> None:
    with ACCESS_LOG.open("a", encoding="utf-8") as handle:
        handle.write(
            f"| {RUN_ID} | {utc_now()} | {status} | "
            "`data/training_company_split/test.csv` | "
            f"`{MANIFEST.relative_to(ROOT).as_posix()}` | {note} |\n"
        )


def read_cins(phase0: dict) -> tuple[dict[str, set[str]], dict]:
    cohorts: dict[str, set[str]] = {}
    details = {}
    for name in ("train", "val", "test"):
        file_path = ROOT / "data" / "training_company_split" / f"{name}.csv"
        expected = phase0["dataset_metadata"][name]
        if file_hash(file_path) != expected["sha256"]:
            raise ValueError(f"Frozen {name} CSV hash mismatch")
        cins: set[str] = set()
        rows = 0
        with file_path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "cin" not in reader.fieldnames:
                raise ValueError(f"Missing CIN column in {name} CSV")
            for row in reader:
                cins.add(normalize_cin(row["cin"]))
                rows += 1
        if rows != expected["rows"] or len(cins) != expected["unique_cins"]:
            raise ValueError(f"Frozen {name} row/CIN count mismatch")
        cohorts[name] = cins
        details[name] = {
            "csv_sha256": expected["sha256"],
            "rows": rows,
            "unique_cins": len(cins),
            "cin_set_sha256": cin_digest(cins),
        }
    if any(cohorts[a] & cohorts[b] for a, b in (("train", "val"), ("train", "test"), ("val", "test"))):
        raise ValueError("Frozen CIN cohorts overlap")
    return cohorts, details


def build() -> tuple[bytes, dict]:
    phase0 = json.loads(PHASE0_PATH.read_text(encoding="utf-8"))
    old_audit = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    if phase0.get("status") != "PASS" or old_audit.get("status") != "PASS":
        raise ValueError("Required Phase 0 / legacy exposure audit did not PASS")
    if old_audit.get("decision") != "TRAIN_COMPANY_ONLY_MLM_REQUIRED_AS_LEAKAGE_CONTROL":
        raise ValueError("Legacy exposure decision is not the preregistered leakage-control path")
    if file_hash(CORPUS_IN) != old_audit["saved_corpus"]["sha256"]:
        raise ValueError("Saved legacy corpus hash changed since audit")
    raw_corpus = CORPUS_IN.read_bytes()
    old_lines = raw_corpus.decode("utf-8").splitlines()
    if not old_lines or len(old_lines) != len(set(old_lines)) or any(not s for s in old_lines):
        raise ValueError("Legacy corpus lines are empty/duplicate/invalid")
    old_corpus = set(old_lines)
    if len(old_corpus) != old_audit["saved_corpus"]["unique_sentences"]:
        raise ValueError("Legacy corpus count changed")

    access("METADATA_ONLY_STARTED", "CIN and exact-text embargo check; no labels or model scores")
    cohorts, split_details = read_cins(phase0)
    by_cin = {cin: BITS[name] for name in ("train", "val", "test") for cin in cohorts[name]}
    db_path = Path(old_audit["database"]["path"]).resolve()
    db_before = db_path.stat()
    if db_before.st_size != old_audit["database"]["bytes"]:
        raise ValueError("Database size changed since legacy exposure audit")
    if datetime.fromtimestamp(db_before.st_mtime, timezone.utc).isoformat() != old_audit["database"]["mtime_utc"]:
        raise ValueError("Database mtime changed since legacy exposure audit")

    masks = dict.fromkeys(old_corpus, 0)
    train_cins_by_text: dict[str, set[str]] = {}
    db_only_texts: set[str] = set()
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
            text = normalize_text(raw_value)
            if len(text) < 20:
                continue
            cin = normalize_cin(raw_cin)
            bit = by_cin.get(cin, BITS["outside_split"])
            if text in masks:
                masks[text] |= bit
                if bit == BITS["train"]:
                    train_cins_by_text.setdefault(text, set()).add(cin)
            else:
                db_only_texts.add(text)
    finally:
        conn.close()
    db_after = db_path.stat()
    if (db_before.st_size, db_before.st_mtime_ns) != (db_after.st_size, db_after.st_mtime_ns):
        raise RuntimeError("Database changed during corpus construction")
    if file_hash(CORPUS_IN) != old_audit["saved_corpus"]["sha256"]:
        raise RuntimeError("Saved legacy corpus changed during construction")
    for name in ("train", "val", "test"):
        if file_hash(ROOT / "data" / "training_company_split" / f"{name}.csv") != split_details[name]["csv_sha256"]:
            raise RuntimeError(f"Frozen {name} CSV changed during construction")

    mask_counts = Counter(masks.values())
    labels = {
        "+".join(name for name, bit in BITS.items() if mask & bit) if mask else "unmatched": count
        for mask, count in sorted(mask_counts.items())
    }
    if labels != old_audit["attribution"]["source_masks"]:
        raise ValueError("Current corpus-to-CIN attribution differs from saved exposure audit")
    if len(db_only_texts) != old_audit["attribution"]["current_db_valid_unique_sentences_not_in_saved_corpus"]:
        raise ValueError("DB-only text count differs from saved exposure audit")
    if mask_counts[0]:
        raise ValueError("Some legacy corpus texts cannot be assigned to current DB CINs")

    selected = sorted(text for text, mask in masks.items() if mask == BITS["train"])
    if not selected:
        raise ValueError("No eligible train-only MLM sentences")
    contributing_cins: set[str] = set()
    for text in selected:
        contributing_cins.update(train_cins_by_text[text])
    if not contributing_cins <= cohorts["train"]:
        raise AssertionError("Contributing CIN is not in frozen train cohort")
    if any(masks[text] & (BITS["val"] | BITS["test"] | BITS["outside_split"]) for text in selected):
        raise AssertionError("Val/test/outside text entered the train-only corpus")
    corpus_bytes = ("\n".join(selected) + "\n").encode("utf-8")
    excluded_shared = sum(n for mask, n in mask_counts.items() if (mask & 1) and (mask & 6))

    manifest = {
        "schema_version": 1,
        "run_id": RUN_ID,
        "phase": "PHASE_1_TRAIN_ONLY_MLM_CORPUS",
        "status": "PASS",
        "verdict": "LEAKAGE CONTROL; not an accuracy improvement",
        "training": "NOT RUN",
        "inference": "NOT RUN",
        "test_performance": "NOT RUN",
        "selection_rule": "saved legacy corpus sentence with current DB mask == train only",
        "old_corpus_path": CORPUS_IN.relative_to(ROOT).as_posix(),
        "old_corpus_sha256": old_audit["saved_corpus"]["sha256"],
        "old_corpus_unique_sentences": len(old_corpus),
        "new_corpus_path": CORPUS_OUT.relative_to(ROOT).as_posix(),
        "new_corpus_sha256": digest(corpus_bytes),
        "new_corpus_unique_sentences": len(selected),
        "new_corpus_bytes": len(corpus_bytes),
        "all_train_cins": sorted(cohorts["train"]),
        "all_train_cin_count": len(cohorts["train"]),
        "all_train_cin_set_sha256": cin_digest(cohorts["train"]),
        "contributing_cins": sorted(contributing_cins),
        "contributing_cin_count": len(contributing_cins),
        "contributing_cin_set_sha256": cin_digest(contributing_cins),
        "validation_cin_count": len(cohorts["val"]),
        "test_cin_count": len(cohorts["test"]),
        "validation_test_contributing_cins": 0,
        "exact_sentence_overlap_with_validation_or_test_db_text": 0,
        "excluded_old_corpus_sentences": len(old_corpus) - len(selected),
        "excluded_train_shared_with_validation_or_test_sentences": excluded_shared,
        "excluded_current_db_only_sentences": len(db_only_texts),
        "source_masks_rechecked": labels,
        "split_metadata": split_details,
        "database_path": str(db_path),
        "database_bytes": db_before.st_size,
        "database_mtime_utc": datetime.fromtimestamp(db_before.st_mtime, timezone.utc).isoformat(),
        "legacy_exposure_audit_run_id": old_audit["run_id"],
        "legacy_exposure_audit_sha256": file_hash(AUDIT_PATH),
        "phase0_run_id": phase0["run_id"],
        "prereg_sha256": file_hash(IMPROVE / "prereg.md"),
        "script_sha256": file_hash(Path(__file__)),
        "environment": environment(),
        "completed_at_utc": utc_now(),
    }
    return corpus_bytes, manifest


def main() -> None:
    if CORPUS_OUT.exists() or MANIFEST.exists():
        raise FileExistsError("Train-only corpus/manifest already exists; refusing overwrite")
    ledger("RUNNING", "RUNNING", MANIFEST)
    try:
        corpus_bytes, manifest = build()
        with CORPUS_OUT.open("xb") as handle:
            handle.write(corpus_bytes)
        if file_hash(CORPUS_OUT) != manifest["new_corpus_sha256"]:
            raise RuntimeError("Written train-only corpus hash mismatch")
        with MANIFEST.open("x", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, ensure_ascii=False)
            handle.write("\n")
        access("METADATA_ONLY_PASS", "Exact-text embargo verified; no model scores")
        ledger("PASS", manifest["verdict"], MANIFEST)
        print(f"Train-only MLM corpus: PASS; {manifest['new_corpus_unique_sentences']} unique sentences from {manifest['contributing_cin_count']} train CINs")
        print(f"Excluded train/shared val-test sentences: {manifest['excluded_train_shared_with_validation_or_test_sentences']}")
        print(f"Exact val/test sentence overlap in new corpus: {manifest['exact_sentence_overlap_with_validation_or_test_db_text']}")
        print(f"Corpus: {CORPUS_OUT}")
        print(f"Manifest: {MANIFEST}")
        print("Training/inference/test performance: NOT RUN")
    except Exception as exc:
        failure = IMPROVE / f"train_only_mlm_corpus_failure_{RUN_ID}.json"
        with failure.open("x", encoding="utf-8") as handle:
            json.dump(
                {"run_id": RUN_ID, "status": "FAIL", "error_type": type(exc).__name__,
                 "error": str(exc), "training": "NOT RUN", "test_performance": "NOT RUN",
                 "completed_at_utc": utc_now()},
                handle, indent=2,
            )
            handle.write("\n")
        access("METADATA_ONLY_FAIL", "Corpus construction failed; see failure JSON")
        ledger("FAIL", type(exc).__name__, failure)
        print(f"Train-only MLM corpus: FAIL — {type(exc).__name__}: {exc}")
        print(f"Failure: {failure}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
