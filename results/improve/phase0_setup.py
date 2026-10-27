"""User-run Phase 0 metadata capture; no training, model loading or evaluation.

Run from the repository root with .venv-ml. This inspects environment metadata,
verifies saved audit hashes, and hashes/checks CINs in the frozen CSVs. Test
access is explicitly metadata-only. It never opens AI-label or quarantine data.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from datetime import datetime, timezone


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "results" / "improve"
LABEL_PROVENANCE = (
    "agreement with taxonomy-derived weak labels (partly AI-assisted mapping)"
)
SEEDS = {"training": 42, "bootstrap": 4206, "concept_holdouts": [42, 17, 73]}
LEDGER_FIELDS = [
    "id", "hypothesis", "config", "val_metric", "test_metric", "verdict",
    "status", "result_json",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def git_bytes(*args: str) -> bytes:
    proc = subprocess.run(
        ["git", *args], cwd=ROOT, capture_output=True, check=False,
        timeout=30,
    )
    if proc.returncode:
        raise RuntimeError(
            "Git metadata command failed: "
            + proc.stderr.decode("utf-8", errors="replace").strip()
        )
    return proc.stdout


def persist(path: Path, report: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".writing")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")
    os.replace(temporary, path)


def test_log(event_id: str, event: str, output: Path, note: str) -> None:
    # This is metadata access, never a prediction/metric evaluation.
    with (OUT_DIR / "test_access_log.md").open(
        "a", encoding="utf-8", newline="\n"
    ) as handle:
        handle.write(
            f"| {event_id} | {utc_now()} | METADATA_ONLY_{event} | "
            f"`data/training_company_split/test.csv` | "
            f"`{output.relative_to(ROOT).as_posix()}` | {note} |\n"
        )


def environment() -> dict:
    packages = {}
    for name in (
        "torch", "transformers", "sentence-transformers", "datasets",
        "accelerate", "safetensors", "tokenizers", "numpy", "pandas",
        "scipy", "scikit-learn", "xgboost",
    ):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None

    result = {
        "python_executable": sys.executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "package_versions": packages,
        "git_commit": git_bytes("rev-parse", "HEAD").decode().strip(),
        "tracked_diff_sha256": digest(git_bytes(
            "diff", "--no-ext-diff", "--no-textconv", "--binary", "HEAD"
        )),
        "worktree_dirty": bool(git_bytes("status", "--porcelain")),
        "torch_device_query_status": "NOT RUN",
    }
    try:
        import torch

        result["torch_device_query_status"] = "COMPLETED_NO_MODEL_LOAD"
        result["cuda_available"] = bool(torch.cuda.is_available())
        result["torch_cuda_version"] = torch.version.cuda
        result["gpus"] = [
            {
                "index": index,
                "name": torch.cuda.get_device_properties(index).name,
                "total_memory_bytes": int(
                    torch.cuda.get_device_properties(index).total_memory
                ),
            }
            for index in range(torch.cuda.device_count())
        ]
    except Exception as exc:
        result["torch_device_query_status"] = "FAILED"
        result["torch_device_query_error"] = f"{type(exc).__name__}: {exc}"
    return result


def split_metadata(path: Path) -> tuple[dict, set[str]]:
    before = file_sha256(path)
    cins: set[str] = set()
    rows = 0
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if "cin" not in (reader.fieldnames or []):
            raise ValueError(f"Missing CIN column: {path.relative_to(ROOT)}")
        for row in reader:
            cin = str(row.get("cin") or "").strip().upper()
            if not cin or cin in {"NAN", "NONE", "NULL"}:
                raise ValueError(f"Blank/invalid CIN at CSV record {rows + 1}")
            cins.add(cin)
            rows += 1
    if file_sha256(path) != before:
        raise RuntimeError("Split file changed during metadata capture")
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": before,
        "rows": rows,
        "unique_cins": len(cins),
        "sorted_cin_set_sha256": digest("\n".join(sorted(cins)).encode()),
        "access_role": "METADATA_ONLY: SHA256 and CIN accounting; no metrics",
    }, cins


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=OUT_DIR / "phase0_setup.json")
    args = parser.parse_args()
    output = args.output.resolve()
    if OUT_DIR.resolve() not in output.parents:
        raise ValueError("Output must be inside results/improve")
    if not output.parent.is_dir():
        raise ValueError("Output parent directory must already exist")

    run_id = "P0-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    report = {
        "schema_version": 1,
        "run_id": run_id,
        "phase": "PHASE_0_METADATA_SETUP",
        "status": "RUNNING",
        "started_at_utc": utc_now(),
        "label_provenance": LABEL_PROVENANCE,
        "seeds_for_future_runs": SEEDS,
        "training": "NOT RUN",
        "model_loading": "NOT RUN",
        "inference": "NOT RUN",
        "bootstrap_metrics": "NOT RUN",
        "new_test_evaluations_in_this_run": 0,
        "historical_test_evaluation_count": None,
        "historical_test_count_note": "Already evaluated; exact lifetime count unknown",
        "encoder_choice": "USER_SELECTED_TRAIN_COMPANY_ONLY_MLM_ADAPTATION",
        "next_phase": "STOP_AFTER_PHASE_0_REVIEW",
        "errors": [],
    }
    # Refuse overwrite before doing work. Interrupted/failed files stay evidence.
    with output.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2)
        handle.write("\n")

    metadata_started = False
    try:
        report["environment"] = environment()
        report["script_sha256"] = file_sha256(Path(__file__).resolve())
        report["prereg_sha256"] = file_sha256(OUT_DIR / "prereg.md")
        snapshot_path = OUT_DIR / "baseline_snapshot.json"
        report["baseline_snapshot_sha256"] = file_sha256(snapshot_path)
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
        report["source_hash_verification"] = {}
        for name, source in snapshot["sources"].items():
            source_path = ROOT / source["original_path"]
            actual = file_sha256(source_path)
            report["source_hash_verification"][name] = {
                "expected_sha256": source["sha256"],
                "actual_sha256": actual,
                "matches": actual == source["sha256"],
            }
            if actual != source["sha256"]:
                raise RuntimeError(f"Audit source changed after Phase 0 import: {name}")

        report["dataset_metadata"] = {}
        split_cins = {}
        test_log(run_id, "STARTED", output, "Hash/CIN check only; no prediction")
        metadata_started = True
        for split in ("train", "val", "test"):
            metadata, cins = split_metadata(
                ROOT / "data" / "training_company_split" / f"{split}.csv"
            )
            report["dataset_metadata"][split] = metadata
            split_cins[split] = cins

        overlaps = {
            f"{a}_vs_{b}": len(split_cins[a] & split_cins[b])
            for a, b in (("train", "val"), ("train", "test"), ("val", "test"))
        }
        report["pairwise_cin_overlap"] = overlaps
        if any(overlaps.values()):
            raise RuntimeError("Frozen company split has CIN overlap")

        source = snapshot["sources"]["stage3_seed99_recovered_full_results.json"]["data"]
        if report["dataset_metadata"]["test"]["sha256"] != source["test_sha256"]:
            raise RuntimeError("Current test hash differs from the recovered audit")
        if report["dataset_metadata"]["test"]["rows"] != source["n_segments"]:
            raise RuntimeError("Current test N differs from the recovered audit")
        if report["dataset_metadata"]["test"]["unique_cins"] != source["n_company_clusters_cin"]:
            raise RuntimeError("Current test CIN count differs from the recovered audit")
        if report["environment"]["torch_device_query_status"] == "FAILED":
            raise RuntimeError("Torch/GPU metadata query failed; see environment field")
        if file_sha256(OUT_DIR / "prereg.md") != report["prereg_sha256"]:
            raise RuntimeError("Preregistration changed during metadata capture")
        report["status"] = "PASS"
    except Exception as exc:
        report["status"] = "FAIL"
        report["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        report["finished_at_utc"] = utc_now()
        persist(output, report)
        if metadata_started:
            test_log(run_id, report["status"], output, "No model/test evaluation performed")
        with (OUT_DIR / "experiment_ledger.csv").open(
            "a", encoding="utf-8", newline=""
        ) as handle:
            writer = csv.DictWriter(handle, fieldnames=LEDGER_FIELDS)
            writer.writerow({
                "id": run_id,
                "hypothesis": "Metadata integrity prerequisite; not an ML experiment",
                "config": "phase0_setup.py",
                "val_metric": "NOT RUN",
                "test_metric": "NOT RUN",
                "verdict": report["status"],
                "status": report["status"],
                "result_json": output.relative_to(ROOT).as_posix(),
            })

    print("Phase 0 metadata status:", report["status"])
    print("Results:", output)
    print("Training/inference/test metrics: NOT RUN")
    for error in report["errors"]:
        print("ERROR:", error)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
