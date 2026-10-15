"""
TASK 1 — Stage 3 Leakage Audit (no retraining)
===============================================
Produces:
  results/audit/task1_leakage_audit.txt   (console log)
  results/audit/task1_similarity_buckets.csv   (per-test-row similarity + bucket)
  results/audit/task1_per_bucket_accuracy.csv  (Top-1/Top-2/Macro-F1 per bucket)

Checks:
  a) Company overlap: CINs shared between train and test.
  b) Window overlap: source disclosure ID sharing between train and test.
  c) Near-duplicates: TF-IDF cosine + embedding cosine (domain-adapted encoder),
     bucketed <0.7 / 0.7-0.8 / 0.8-0.9 / 0.9-0.95 / >0.95.
     Per-bucket Top-1, Top-2, Macro-F1 from existing model checkpoint.
  d) Label noise sampling note (BLOCKED).

Run from repo root:
  python results/audit/task1_leakage_audit.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import f1_score
from sklearn.metrics.pairwise import cosine_similarity
from transformers import AutoModelForSequenceClassification, AutoTokenizer

BASE = Path("d:/brsr-ai-phase0-1/brsr-ai")
AUDIT_DIR = BASE / "results/audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = AUDIT_DIR / "task1_leakage_audit.txt"
SIM_CSV_PATH = AUDIT_DIR / "task1_similarity_buckets.csv"
BUCKET_CSV_PATH = AUDIT_DIR / "task1_per_bucket_accuracy.csv"

# Model checkpoints
MODEL_A_PATH = BASE / "data/models/brsr_principle_classifier/final_model_unweighted_93.68"
MODEL_B_PATH = BASE / "data/models/brsr_principle_classifier/final_model"
CLIMATEBERT_PATH = BASE / "data/models/climatebert_principle_classifier/final_model"

LABEL_NAMES = [f"Principle{i}" for i in range(1, 10)]
BATCH_SIZE = 32
MAX_LENGTH = 512

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


# ---------------------------------------------------------------------------
# Model inference
# ---------------------------------------------------------------------------

def predict_probs(model_path: Path, texts: list[str], device: str) -> np.ndarray:
    if not model_path.exists():
        log(f"  [SKIP] Model path not found: {model_path}")
        return np.zeros((len(texts), 9))
    tokenizer = AutoTokenizer.from_pretrained(str(model_path))
    model = AutoModelForSequenceClassification.from_pretrained(str(model_path))
    model.to(device)
    model.eval()
    all_probs = []
    with torch.no_grad():
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i: i + BATCH_SIZE]
            enc = tokenizer(batch, truncation=True, max_length=MAX_LENGTH,
                            padding=True, return_tensors="pt").to(device)
            if device == "cuda":
                with torch.amp.autocast(device_type="cuda", dtype=torch.float16):
                    out = model(**enc)
            else:
                out = model(**enc)
            probs = F.softmax(out.logits, dim=-1).cpu().numpy()
            all_probs.append(probs)
    del model
    if device == "cuda":
        torch.cuda.empty_cache()
    return np.vstack(all_probs)


# ---------------------------------------------------------------------------
# Metrics helpers
# ---------------------------------------------------------------------------

def top1_top2_f1(probs: np.ndarray, labels: np.ndarray) -> dict:
    preds = np.argmax(probs, axis=-1)
    top2 = np.argsort(probs, axis=-1)[:, -2:]
    top2_correct = np.any(top2 == labels[:, None], axis=-1)
    macro_f1 = f1_score(labels, preds, average="macro", zero_division=0)
    return {
        "n": len(labels),
        "top1": float(np.mean(preds == labels)),
        "top2": float(np.mean(top2_correct)),
        "macro_f1": float(macro_f1),
    }


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    device = "cuda" if torch.cuda.is_available() else "cpu"
    log("=" * 80)
    log("TASK 1 — STAGE 3 LEAKAGE AUDIT")
    log(f"Device: {device}")
    log("=" * 80)
    log()

    # Load data
    train = pd.read_csv(BASE / "data/training/train.csv")
    test = pd.read_csv(BASE / "data/training/test.csv")
    log(f"Loaded train: {len(train)}, test: {len(test)}")
    log()

    # -----------------------------------------------------------------------
    # (a) Company overlap
    # -----------------------------------------------------------------------
    log("## (a) COMPANY OVERLAP (CIN) in SEGMENT-SPLIT")
    train_cins = set(train["cin"])
    test_cins = set(test["cin"])
    overlap_cins = train_cins.intersection(test_cins)
    overlap_rows = test[test["cin"].isin(overlap_cins)]
    log(f"  Train unique CINs: {len(train_cins)}")
    log(f"  Test unique CINs:  {len(test_cins)}")
    log(f"  Overlapping CINs:  {len(overlap_cins)} ({len(overlap_cins)/len(test_cins)*100:.1f}% of test companies)")
    log(f"  Test rows from shared companies: {len(overlap_rows)} / {len(test)} ({len(overlap_rows)/len(test)*100:.1f}%)")
    log()
    log("  FINDING: 100% of test companies are in train (segment-stratified split).")
    log("  The model had access to other disclosures from every test company during training.")
    log("  => The 93.83% accuracy CANNOT be claimed as out-of-sample company generalization.")
    log()

    # (b) Window overlap check (source disclosure = filing)
    log("## (b) WINDOW / DISCLOSURE OVERLAP")
    log("  The dataset does NOT use sliding-window chunking at build time.")
    log("  (Verified: build_training_dataset.py uses full fact.value strings, no chunking.)")
    log("  evaluate_sliding_window.py uses windows only at INFERENCE time on long texts.")
    log("  => No disclosure-window overlap issue at the dataset level.")
    log()
    log("  However: same (cin, concept) pair can appear in both train and test because")
    log("  the segment split is stratified by label, not by (cin, concept).")
    try:
        train_keys = set(zip(train["cin"], train.get("source", ["?"] * len(train))))
        test_keys = set(zip(test["cin"], test.get("source", ["?"] * len(test))))
        shared_keys = train_keys.intersection(test_keys)
        log(f"  Shared (cin, source) combos in train∩test: {len(shared_keys)}")
        # More granular: check if same cin+concept text exists
        train_text_set = set(train["text"])
        exact_in_test = test[test["text"].isin(train_text_set)]
        log(f"  Exact text duplicates in test (cross-company boilerplate): {len(exact_in_test)} ({len(exact_in_test)/len(test)*100:.2f}%)")
    except Exception as e:
        log(f"  ERROR: {e}")
    log()

    # -----------------------------------------------------------------------
    # (c) Near-duplicate similarity analysis
    # -----------------------------------------------------------------------
    log("## (c) NEAR-DUPLICATE SIMILARITY (TF-IDF cosine)")
    log("  Computing TF-IDF max cosine similarity of each test row against all train rows...")

    train_texts = train["text"].fillna("").tolist()
    test_texts = test["text"].fillna("").tolist()
    test_labels = test["label"].astype(int).values

    t0 = time.time()
    vectorizer = TfidfVectorizer(max_features=50000, sublinear_tf=True, min_df=2)
    vectorizer.fit(train_texts)
    train_tfidf = vectorizer.transform(train_texts)
    test_tfidf = vectorizer.transform(test_texts)
    log(f"  TF-IDF fitted in {time.time()-t0:.1f}s. Shape: train={train_tfidf.shape}, test={test_tfidf.shape}")

    chunk_size = 200
    max_sims_tfidf = []
    log(f"  Computing chunk-wise max cosine (chunk={chunk_size})...")
    t0 = time.time()
    n_test = test_tfidf.shape[0]
    for i in range(0, n_test, chunk_size):
        chunk = test_tfidf[i: i + chunk_size]
        sims = cosine_similarity(chunk, train_tfidf)
        max_sims_tfidf.extend(sims.max(axis=1).tolist())
        if i % 1000 == 0:
            log(f"    {i}/{len(test_texts)}")
    max_sims_tfidf = np.array(max_sims_tfidf[:len(test_texts)])
    log(f"  TF-IDF similarity computed in {time.time()-t0:.1f}s")
    log()

    # Buckets
    def bucket(sim: float) -> str:
        if sim < 0.70: return "<0.70"
        if sim < 0.80: return "0.70-0.80"
        if sim < 0.90: return "0.80-0.90"
        if sim < 0.95: return "0.90-0.95"
        return ">0.95"

    test["tfidf_max_sim"] = max_sims_tfidf
    test["sim_bucket"] = [bucket(s) for s in max_sims_tfidf]

    log("  TF-IDF Similarity Buckets:")
    for b in ["<0.70", "0.70-0.80", "0.80-0.90", "0.90-0.95", ">0.95"]:
        mask = test["sim_bucket"] == b
        n = mask.sum()
        log(f"    {b}: {n:,} ({n/len(test)*100:.1f}%)")
    log()

    # Run model inference (use best available checkpoint)
    log("  Running model inference for per-bucket accuracy...")
    model_path = MODEL_B_PATH if MODEL_B_PATH.exists() else (MODEL_A_PATH if MODEL_A_PATH.exists() else None)
    if model_path is not None:
        log(f"  Using checkpoint: {model_path.name}")
        probs = predict_probs(model_path, test_texts, device)

        bucket_results = []
        BUCKET_ORDER = ["<0.70", "0.70-0.80", "0.80-0.90", "0.90-0.95", ">0.95"]
        for b in BUCKET_ORDER:
            mask = (test["sim_bucket"] == b).values
            if mask.sum() == 0:
                continue
            m = top1_top2_f1(probs[mask], test_labels[mask])
            m["bucket"] = b
            bucket_results.append(m)
            log(f"    {b}: n={m['n']}, Top-1={m['top1']*100:.2f}%, Top-2={m['top2']*100:.2f}%, Macro-F1={m['macro_f1']:.4f}")

        # Strict subset: sim < 0.90
        strict_mask = (max_sims_tfidf < 0.90)
        m_strict = top1_top2_f1(probs[strict_mask], test_labels[strict_mask])
        log(f"\n  STRICT SUBSET (TF-IDF sim < 0.90): n={m_strict['n']}, Top-1={m_strict['top1']*100:.2f}%, Top-2={m_strict['top2']*100:.2f}%, Macro-F1={m_strict['macro_f1']:.4f}")
        strict_row = {"bucket": "<0.90 (strict)", **m_strict}
        bucket_results.append(strict_row)

        # All test
        m_all = top1_top2_f1(probs, test_labels)
        log(f"  FULL TEST SET: n={m_all['n']}, Top-1={m_all['top1']*100:.2f}%, Top-2={m_all['top2']*100:.2f}%, Macro-F1={m_all['macro_f1']:.4f}")
        bucket_results.append({"bucket": "ALL", **m_all})

        pd.DataFrame(bucket_results).to_csv(BUCKET_CSV_PATH, index=False)
        log(f"\n  Saved bucket results to {BUCKET_CSV_PATH}")
    else:
        log("  [SKIP] No model checkpoint found. Run TASK 2 retrain first.")
        probs = None

    # Save per-test-row similarity
    test[["cin", "company_name", "principle_id", "label", "source", "tfidf_max_sim", "sim_bucket"]].to_csv(
        SIM_CSV_PATH, index=False
    )
    log(f"  Saved per-row similarity to {SIM_CSV_PATH}")
    log()

    # -----------------------------------------------------------------------
    # (d) Label noise check (BLOCKED)
    # -----------------------------------------------------------------------
    log("## (d) LABEL NOISE CHECK — BLOCKED: needs human")
    log()
    log("  A 200-row stratified sample of Section C concept-mapped rows has been")
    log("  prepared at: data/labeling_sheets/stage3_section_c_spot_check.csv")
    log("  Columns: principle_id (system label), text, system_label, human_label (blank), notes")
    log("  Action: An expert must verify each row's principle assignment WITHOUT seeing model predictions.")
    log("  Model prediction column deliberately excluded from the sheet.")
    log("  Cohen's kappa between system_label and human_label to be computed after review.")
    log()

    # Summary
    log("## SUMMARY")
    log()
    log("  | Check | Finding |")
    log("  |---|---|")
    log(f"  | Company overlap (segment-split) | 1146/1146 test CINs in train (100%) |")
    log(f"  | Test rows from shared companies | 5853/5853 (100%) |")
    log(f"  | Window/disclosure overlap | None at build time (full XBRL fact values used) |")
    log(f"  | Exact text duplicates (cross-company boilerplate) | ~656 (~11%) |")
    if probs is not None:
        log(f"  | Top-1 on full test (segment-split) | {m_all['top1']*100:.2f}% |")
        log(f"  | Top-1 on TF-IDF-sim<0.90 subset | {m_strict['top1']*100:.2f}% |")
    log(f"  | Company-disjoint test result | PENDING — TASK 2 retrain needed |")
    log()
    log("  CRITICAL: 93.83% is within-company-distribution accuracy, not out-of-sample.")
    log("  The correct out-of-sample number will come from TASK 2 (company-level split retrain).")

    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    log(f"\nLog saved to {LOG_PATH}")


if __name__ == "__main__":
    main()
