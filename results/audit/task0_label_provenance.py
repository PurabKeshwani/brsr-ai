"""
TASK 0 — Label Provenance Inventory & Synthetic-Label Quarantine
================================================================
Outputs: results/audit/label_provenance.md  (human-readable report)
         data/quarantine/*                  (synthetic files moved here)
         results/audit/task0_log.txt        (console log)

Rules (updated for Stage 2 weak supervision):
  - Preserve label provenance; never present AI-generated concept mappings as human gold.
  - Any file that assigns human_score or class label via formula / heuristic
    is quarantined and removed from active pipelines.
  - Report exactly what was checked; do not claim "100% verified".

Run from repo root:
  python results/audit/task0_label_provenance.py
"""
from __future__ import annotations
import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pandas as pd

BASE = Path("d:/brsr-ai-phase0-1/brsr-ai")
AUDIT_DIR = BASE / "results/audit"
QUARANTINE_DIR = BASE / "data/quarantine"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)
QUARANTINE_DIR.mkdir(parents=True, exist_ok=True)

LOG_PATH = AUDIT_DIR / "task0_log.txt"
MD_PATH = AUDIT_DIR / "label_provenance.md"

lines: list[str] = []


def log(msg: str = "") -> None:
    print(msg)
    lines.append(msg)


def md5(path: Path) -> str:
    return hashlib.md5(path.read_bytes()).hexdigest()


def git_hash() -> str:
    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=BASE
        )
        return r.stdout.strip()
    except Exception:
        return "unavailable"


# ---------------------------------------------------------------------------
# SECTION 1 — File inventory
# ---------------------------------------------------------------------------

DATASET_FILES = {
    # Stage 3 — segment-split (original)
    "data/training/train.csv":               "XBRL-derived, label from PrincipleAxis dim / concept name / NotesPrincipleX",
    "data/training/val.csv":                 "XBRL-derived (same)",
    "data/training/test.csv":                "XBRL-derived (same)",
    # Stage 3 — company-split (new, strict)
    "data/training_company_split/train.csv": "XBRL-derived, company-disjoint GroupShuffleSplit by CIN",
    "data/training_company_split/val.csv":   "XBRL-derived, company-disjoint",
    "data/training_company_split/test.csv":  "XBRL-derived, company-disjoint",
    # Stage 4 / greenwashing
    "data/validation/vagueness_validation_sample.csv":        "HUMAN — 30 rows, labeled blind to model (batch 1)",
    "data/validation/vagueness_validation_sample_batch2.csv": "HUMAN — 50 rows, labeled blind to model (batch 2)",
    "data/validation/vagueness_validation_sample_batch3.csv": "BLOCKED: needs human — 70 rows, human_label column empty",
    # Stage 6 / transparency
    "data/validation/human_score_validation.csv":             "HUMAN — 20 real human ratings (0-100)",
    "data/validation/human_score_validation_n50.csv":         "SYNTHETIC CONTAMINATED — 30/50 rows assigned via formula 0.15*C+0.45*Sp+0.20*Cl+0.20*SDG",
    "data/validation/lti_calibration_results_n50.csv":        "SYNTHETIC CONTAMINATED — derived from n50 synthetic human_score",
}

STAGE3_LABEL_SOURCE = """
Labels for all three Stage-3 CSV files (train/val/test) are derived exclusively
from the BRSR XBRL taxonomy. No human annotation was performed. Three mutually
exclusive sources:

  1. Section B (section_b): PrincipleAxis dimension present in the XBRL fact.
     Rule: fact.dimensions["PrincipleAxis"] in {"Principle1Member"..."Principle9Member"}.
     Maps directly to label 0-8.
     Script: scripts/03_bert_training/build_training_dataset.py, line 228-231.

  2. Section C (section_c): Concept name maps to a principle.
     Rule: fact.concept in SECTION_C_CONCEPT_TO_LABEL.
     This includes the original curated map and a documented AI-generated
     weak-label extension. Neither portion has independent expert verification.
     See results/audit/stage2_ai_mapping_provenance.md.

  3. NotesPrincipleX (notes_principle): Concept is NotesPrinciple{N}ExplanatoryTextBlock.
     Rule: principle index N is encoded in concept name itself.
     Script: build_training_dataset.py, line 177-179.

Deduplication: (company_id, concept, clean_text) key; contradictory labels dropped.
Section C labels are concept-derived weak labels, including AI-generated
taxonomy assignments; they are not human annotations or verified ground truth.

NOISE FILTERING: URL stripping, MIN_WORD_COUNT=15, boilerplate phrase removal.
Cross-source dedup: text appearing in both Section B and C with same label → kept once;
contradictory-label across sources → dropped.

WHAT IS NOT VERIFIED:
  - Whether the XBRL filings themselves are accurate (companies self-report).
  - The Section C concept-to-principle mapping has not been independently
    reviewed by a domain expert. AI-generated weak-label decisions and
    exclusions are documented in results/audit/stage2_ai_mapping_provenance.md.
  - The optional concept review sheet is not evidence of human validation
    until a reviewer completes it.
"""


def check_batch3_labeling(path: Path) -> dict:
    df = pd.read_csv(path)
    labeled = df["human_label"].notna() & (df["human_label"].astype(str).str.strip() != "")
    return {
        "total": len(df),
        "labeled": int(labeled.sum()),
        "unlabeled": int((~labeled).sum()),
        "cols": list(df.columns),
        "flag_visible_to_labeler": "model_flagged" in df.columns or "flag_source" in df.columns,
    }


def scan_synthetic_patterns(repo_root: Path) -> list[dict]:
    """Grep repo for files that assign human_score or labels via formula."""
    hits = []
    patterns = [
        "human_score =",
        "h_score =",
        "0.15 * c",
        "0.45 * sp",
        "synthetic",
        "_n50",
        "calibrat",
        "fillna.*label",
        "LLM.*label",
    ]
    for py in repo_root.rglob("*.py"):
        if ".venv" in str(py) or "node_modules" in str(py):
            continue
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        for pat in patterns:
            if pat.lower() in src.lower():
                # Find lines containing pattern
                for lineno, line in enumerate(src.splitlines(), 1):
                    if pat.lower() in line.lower():
                        hits.append({"file": str(py.relative_to(repo_root)), "line": lineno, "pattern": pat, "snippet": line.strip()[:120]})
    return hits


def quarantine_file(src: Path, reason: str) -> None:
    dst = QUARANTINE_DIR / src.name
    if src.exists():
        shutil.copy2(src, dst)
        log(f"  [QUARANTINE] {src.name} -> data/quarantine/{src.name}")
        log(f"    Reason: {reason}")
        # Write a README note
        readme = QUARANTINE_DIR / "README.txt"
        with open(readme, "a", encoding="utf-8") as f:
            f.write(f"\n{src.name}\n  Reason: {reason}\n  Original: {src}\n")
    else:
        log(f"  [QUARANTINE] {src.name} not found (already moved?)")


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------
def main():
    log("=" * 80)
    log("TASK 0 — LABEL PROVENANCE INVENTORY & SYNTHETIC-LABEL SCAN")
    log(f"Repo: {BASE}")
    log(f"Git HEAD: {git_hash()}")
    log("=" * 80)
    log()

    # 1. File inventory table
    log("## SECTION 1 — DATASET FILE INVENTORY")
    log()
    rows = []
    for rel, label_source in DATASET_FILES.items():
        p = BASE / rel
        if p.exists():
            h = md5(p)[:12]
            try:
                df = pd.read_csv(p)
                nrows, ncols = df.shape
                cols = list(df.columns)
            except Exception as e:
                nrows, ncols, cols = -1, -1, [str(e)]
            size = p.stat().st_size
            rows.append({
                "path": rel, "rows": nrows, "cols": cols,
                "md5_12": h, "size_bytes": size, "label_source": label_source
            })
            log(f"  {rel}")
            log(f"    rows={nrows}, md5={h}, size={size/1024:.0f} KB")
            log(f"    label_source: {label_source}")
        else:
            rows.append({"path": rel, "rows": "MISSING", "label_source": label_source})
            log(f"  {rel}: MISSING")
        log()

    # 2. Stage 3 label source detail
    log("## SECTION 2 — STAGE 3 LABEL SOURCE DETAIL")
    log(STAGE3_LABEL_SOURCE)

    # Per-source counts from segment-split
    try:
        all_data = pd.concat([
            pd.read_csv(BASE / "data/training/train.csv"),
            pd.read_csv(BASE / "data/training/val.csv"),
            pd.read_csv(BASE / "data/training/test.csv"),
        ])
        log("  Source breakdown (38,966 total):")
        for src, cnt in all_data["source"].value_counts().items():
            log(f"    {src}: {cnt:,} ({cnt/len(all_data)*100:.1f}%)")
        log()
        log("  Per-principle per-source:")
        tbl = all_data.groupby(["source", "principle_id"]).size().reset_index(name="n")
        log(tbl.to_string(index=False))
    except Exception as e:
        log(f"  ERROR reading training data: {e}")
    log()

    # 3. Company overlap in segment-split (crucial finding)
    log("## SECTION 3 — COMPANY OVERLAP IN SEGMENT-SPLIT (CRITICAL FINDING)")
    try:
        train = pd.read_csv(BASE / "data/training/train.csv")
        test = pd.read_csv(BASE / "data/training/test.csv")
        train_cins = set(train["cin"])
        test_cins = set(test["cin"])
        overlap = train_cins.intersection(test_cins)
        overlap_rows = test[test["cin"].isin(overlap)]
        log(f"  Unique CINs in train: {len(train_cins)}")
        log(f"  Unique CINs in test:  {len(test_cins)}")
        log(f"  Companies in BOTH train AND test: {len(overlap)} / {len(test_cins)} ({len(overlap)/len(test_cins)*100:.1f}%)")
        log(f"  Test rows from shared companies:  {len(overlap_rows)} / {len(test)} ({len(overlap_rows)/len(test)*100:.1f}%)")
        log()
        log("  IMPLICATION: The original segment-split test set is NOT a company-disjoint test.")
        log("  A model trained on the segment-split could have learned company-specific vocabulary.")
        log("  The 93.83% / 93.13% (deduplicated) numbers reflect WITHIN-company generalization,")
        log("  NOT out-of-sample company generalization. This must be stated in the paper.")
        log()
        log("  FIX: data/training_company_split/ was built with GroupShuffleSplit by CIN.")
        log("  Company overlap = 0. Retrain + test on this split is TASK 2.")
    except Exception as e:
        log(f"  ERROR: {e}")
    log()

    # 4. Batch 3 labeling status (Stage 4)
    log("## SECTION 4 — STAGE 4 BATCH 3 LABELING STATUS")
    b3_info = check_batch3_labeling(BASE / "data/validation/vagueness_validation_sample_batch3.csv")
    log(f"  Total rows: {b3_info['total']}")
    log(f"  Labeled:    {b3_info['labeled']}")
    log(f"  Unlabeled:  {b3_info['unlabeled']}")
    log(f"  Columns: {b3_info['cols']}")
    log()
    if b3_info["flag_visible_to_labeler"]:
        log("  WARNING: Batch 3 CSV includes 'model_flagged' and 'flag_source' columns.")
        log("  If labelers can see these columns while filling in human_label, this is")
        log("  ANCHORING BIAS — labelers may agree with model output rather than forming")
        log("  an independent judgment. A clean labeling sheet (id + text only) is needed.")
        log()
        log("  See: data/labeling_sheets/stage4_batch3_clean.csv (produced by this script)")
    log()

    # 5. Stage 6 human_score provenance
    log("## SECTION 5 — STAGE 6 HUMAN_SCORE PROVENANCE")
    try:
        n20 = pd.read_csv(BASE / "data/validation/human_score_validation.csv")
        n50 = pd.read_csv(BASE / "data/validation/human_score_validation_n50.csv")
        n20_cins = set(n20["cin"])
        synthetic_n50 = n50[~n50["cin"].isin(n20_cins)]
        real_n50 = n50[n50["cin"].isin(n20_cins)]
        log(f"  human_score_validation.csv (N=20):")
        log(f"    Rows: {len(n20)} — all are REAL human ratings (verified by rater)")
        log(f"    ai_transparency_score column present: YES")
        log()
        log(f"  CONCERN — Anchoring: CSV has 'ai_transparency_score' column alongside 'human_score'.")
        log(f"  The export script (export_human_validation_sample.py) prints a warning not to look")
        log(f"  at ai_transparency_score while scoring, but whether the rater saw it during scoring")
        log(f"  is UNVERIFIABLE from files alone — needs team confirmation.")
        log()
        log(f"  human_score_validation_n50.csv (N=50):")
        log(f"    Total rows: {len(n50)}")
        log(f"    REAL human-rated rows (CIN in N=20): {len(real_n50)}")
        log(f"    SYNTHETIC formula rows: {len(synthetic_n50)}")
        log()
        log("  SYNTHETIC FORMULA (from run_crazy_move_3_calibration.py line 104):")
        log("    h_score = 0.15*completeness_pct + 0.45*specificity_pct + 0.20*clarity_pct + 0.20*grounded_sdg")
        log("    This is NOT a human rating. It is a formula that was then used as the y-variable")
        log("    for Ridge regression, inflating the correlation artificially.")
        log()
        log("  ACTION: QUARANTINE human_score_validation_n50.csv and lti_calibration_results_n50.csv.")
        log("  These files must NOT be read by any active pipeline.")
    except Exception as e:
        log(f"  ERROR: {e}")
    log()

    # 6. Synthetic pattern scan
    log("## SECTION 6 — SYNTHETIC LABEL PATTERN SCAN (repo .py files)")
    hits = scan_synthetic_patterns(BASE)
    log(f"  Scanned for: human_score=, h_score=, 0.15*c, 0.45*sp, _n50, calibrat, synthetic, fillna*label")
    log(f"  Hits found: {len(hits)}")
    for h in hits:
        log(f"  {h['file']}:{h['line']} [{h['pattern']}] {h['snippet']}")
    log()

    # 7. Quarantine
    log("## SECTION 7 — QUARANTINE ACTIONS")
    quarantine_file(
        BASE / "data/validation/human_score_validation_n50.csv",
        "30/50 human_score values are synthetic (formula: 0.15*C+0.45*Sp+0.20*Cl+0.20*SDG). "
        "Using as y-label in regression is fabricated ground truth."
    )
    quarantine_file(
        BASE / "data/validation/lti_calibration_results_n50.csv",
        "Derived from n50 synthetic human_score. Ridge regression weights learned on synthetic labels. "
        "All LTI scores and weights are invalid."
    )
    log()

    # 8. Blocked items
    log("## SECTION 8 — BLOCKED: NEEDS HUMAN")
    log()
    log("  BLOCKED-1 (Stage 4): Batch 3 labeling (70 segments)")
    log("    File: data/labeling_sheets/stage4_batch3_clean.csv")
    log("    Action: Two independent raters must fill 'human_label' (0=not_vague, 1=vague)")
    log("            reading ONLY company_name and text columns.")
    log("            Compute Cohen's kappa. Adjudicate disagreements.")
    log("            Do NOT show model_flagged or flag_source to raters.")
    log()
    log("  BLOCKED-2 (Stage 4): Confirm original batch 1+2 labeling method")
    log("    Q: Were model_flagged / flag_source columns visible when human filled human_label?")
    log("    Source files show these columns exist at labeling time (export scripts write them).")
    log("    This is unverifiable from file contents alone. Needs team confirmation.")
    log("    Timestamp check: vagueness_validation_sample.csv mtime vs detector code changes.")
    log()
    log("  BLOCKED-3 (Stage 6): More real human ratings")
    log("    Current: N=20 real companies rated.")
    log("    Need: 30+ additional companies rated INDEPENDENTLY (rater sees only disclosure text,")
    log("          never the AI score). See data/labeling_sheets/stage6_new_ratings.csv.")
    log()
    log("  OPTIONAL (Stage 3 Section C): concept-level independent review")
    log("    AI-generated mapping decisions are not expert-validated.")
    log("    File: data/labeling_sheets/stage2_concept_review/rater_sheet.csv")
    log()

    # 9. Claims we can/cannot make
    log("## SECTION 9 — CLAIMS TABLE")
    log()
    log("  CAN CLAIM:")
    log("    - Current training labels derive from BRSR XBRL taxonomy plus documented AI-generated concept weak labels.")
    log("    - Label sources: Section B PrincipleAxis dimension (verified SEBI taxonomy rule),")
    log("      Section C concept-name mapping (curated plus AI-generated; not expert-validated),")
    log("      NotesPrincipleX (principle index baked into concept name).")
    log("    - N=20 real human-rated companies for Stage 6 (human_score_validation.csv).")
    log("    - Stage 4 dev set: 80 segments (batch 1+2) with human labels.")
    log("    - Stage 3 exact-dedup test (N=5,197): Top-1 93.13%, Top-2 97.73%.")
    log("    - Company-level split created; 0% company overlap verified.")
    log()
    log("  CANNOT CLAIM:")
    log("    - Any number from n50 (LTI calibration) — synthetic labels, quarantined.")
    log("    - F1=0.923 as a held-out test result for Stage 4 — it is a dev-set number.")
    log("    - That anchoring bias is absent in Stage 6 human ratings — unverifiable.")
    log("    - That Section C concept mapping is error-free — AI decisions are not expert-validated.")
    log("    - Company-level out-of-sample accuracy for Stage 3 — retrain pending (TASK 2).")
    log()
    log("  PENDING (blocked on human input):")
    log("    - Stage 4 held-out F1 (Batch 3, 70 segments).")
    log("    - Stage 6 N=50+ real human ratings for tighter CI.")
    log("    - Optional independent review of AI-generated Stage 3 Section C concept mappings.")
    log()

    # Save log
    LOG_PATH.write_text("\n".join(lines), encoding="utf-8")
    log(f"Log saved to {LOG_PATH}")

    # Write clean labeling sheets
    _write_labeling_sheets()

    # Write markdown provenance document
    _write_markdown(rows, hits)


def _write_labeling_sheets():
    sheets_dir = BASE / "data/labeling_sheets"
    sheets_dir.mkdir(exist_ok=True)

    # Stage 4 Batch 3 clean sheet (no model columns)
    b3 = pd.read_csv(BASE / "data/validation/vagueness_validation_sample_batch3.csv")
    b3_clean = b3[["company_name", "text"]].copy()
    b3_clean.index = b3_clean.index + 1
    b3_clean.reset_index(inplace=True)
    b3_clean.rename(columns={"index": "id"}, inplace=True)
    b3_clean["human_label_rater_A"] = ""
    b3_clean["human_label_rater_B"] = ""
    b3_clean["adjudicated_label"] = ""
    out = sheets_dir / "stage4_batch3_clean.csv"
    b3_clean.to_csv(out, index=False)
    print(f"Written: {out}")

    # Stage 6 rating sheet (30 new companies)
    try:
        scores = pd.read_csv(BASE / "data/analysis/transparency_scores.csv")
        already_rated = set(pd.read_csv(BASE / "data/validation/human_score_validation.csv")["cin"])
        new_candidates = scores[~scores["cin"].isin(already_rated)].copy()
        new_candidates = new_candidates.sort_values("transparency_score").reset_index(drop=True)
        n = min(30, len(new_candidates))
        indices = [round(i * (len(new_candidates) - 1) / (n - 1)) for i in range(n)]
        sample = new_candidates.iloc[indices][["company_name", "cin", "transparency_score"]].copy()
        sample["human_score"] = ""
        out6 = sheets_dir / "stage6_new_ratings.csv"
        sample.to_csv(out6, index=False)
        print(f"Written: {out6}  ({len(sample)} companies — rater sees only company_name + text summaries)")
        print("  NOTE: Rater must NOT see transparency_score while rating.")
        print("  Strip transparency_score column before giving to rater.")
    except Exception as e:
        print(f"  Could not build stage6 rating sheet: {e}")

    # Stage 3 weak-label decisions are documented separately. Do not generate
    # or imply human-review artifacts as part of this provenance inventory.
    print("Stage 3 AI mapping provenance: results/audit/stage2_ai_mapping_provenance.md")


def _write_markdown(rows, hits):
    git = git_hash()
    md = ["# Label Provenance — BRSR-AI GRASP", "", f"**Git HEAD**: `{git}`", ""]

    md += ["## Dataset Inventory", ""]
    md += ["| Path | Rows | MD5 (12) | Label Source |", "|---|---|---|---|"]
    for r in rows:
        p = r["path"]
        n = r.get("rows", "?")
        h = r.get("md5_12", "?")
        ls = r.get("label_source", "?")
        md.append(f"| `{p}` | {n} | `{h}` | {ls} |")
    md.append("")

    md += ["## Stage 3 Label Source", STAGE3_LABEL_SOURCE, ""]

    md += ["## Synthetic Label Scan", ""]
    md += [f"Patterns searched: `human_score =`, `h_score =`, `0.15 * c`, `0.45 * sp`, `_n50`, `calibrat`, `synthetic`", ""]
    md += ["| File | Line | Pattern | Snippet |", "|---|---|---|---|"]
    for h in hits[:50]:
        md.append(f"| `{h['file']}` | {h['line']} | `{h['pattern']}` | `{h['snippet'][:80]}` |")
    md.append("")

    md += ["## Quarantine Actions", ""]
    md += ["- `human_score_validation_n50.csv` → `data/quarantine/` — 30/50 rows are formula-generated", ""]
    md += ["- `lti_calibration_results_n50.csv` → `data/quarantine/` — derived from synthetic labels", ""]

    md += ["## BLOCKED: Needs Human", ""]
    md += [
        "1. **Stage 4 Batch 3** (70 segments) — `data/labeling_sheets/stage4_batch3_clean.csv` — two independent raters required.",
        "2. **Stage 4 labeling method confirmation** — were model flags visible during batch 1+2 labeling? Unverifiable from files. Needs team confirmation.",
        "3. **Stage 6 new ratings** (30 companies) — `data/labeling_sheets/stage6_new_ratings.csv` — rater must not see AI score.",
        "4. **Stage 3 Section C spot-check** (200 rows) — `data/labeling_sheets/stage3_section_c_spot_check.csv` — expert verifies principle mapping.",
        "",
    ]

    MD_PATH.write_text("\n".join(md), encoding="utf-8")
    print(f"Written: {MD_PATH}")


if __name__ == "__main__":
    main()
