"""
Evaluates the combined vagueness detector against the manually-labeled
validation sample (data/validation/vagueness_validation_sample.csv),
computing precision, recall, F1, and AUC-ROC — the metrics the report's
methodology (5.5.2) specifies for the greenwashing detection engine.

Ground truth: human_label column, filled in independently by a project
team member reading only the 'text' column (not the model's prediction) —
see conversation history for the labeling methodology.

Note on sample size: this is a 30-segment validation set, not the report's
stated 200+200 expert-verified reference pool comparison. This should be
described honestly in the paper as a small-sample validation/sanity-check,
with the AUC-ROC reported alongside its sample size — a metric from n=30
carries real uncertainty and should not be presented with the same
confidence as one from a larger held-out set.
"""
import sys
from pathlib import Path

import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

VALIDATION_PATH = Path("data/validation/vagueness_validation_sample.csv")


def main():
    from analysis.vagueness.vagueness_combined import analyze_combined_vagueness  # imported here so the script fails loudly if analysis/ isn't importable, rather than silently using stale CSV data

    df = pd.read_csv(VALIDATION_PATH)

    if df["human_label"].isnull().any():
        missing = df["human_label"].isnull().sum()
        print(f"WARNING: {missing} rows have no human_label filled in — "
              f"these will be excluded from evaluation.")
        df = df.dropna(subset=["human_label"])

    df["human_label"] = df["human_label"].astype(int)

    # CRITICAL: re-run the CURRENT detector on the text now, rather than
    # trusting the 'model_flagged' column exported at sample-creation time.
    # Real bug found and fixed here: an earlier run of this script silently
    # used stale predictions from before a KPI-pattern fix, making the
    # "before" and "after" evaluation results byte-for-byte identical even
    # though the underlying detector code had genuinely changed.
    print("Re-running the current detector on all validation texts (not using cached CSV predictions)...")
    fresh_flags = []
    fresh_sources = []
    for text in df["text"]:
        result = analyze_combined_vagueness(text)
        fresh_flags.append(1 if result.is_flagged_vague else 0)
        fresh_sources.append(result.flag_source)

    df["model_flagged"] = fresh_flags
    df["flag_source"] = fresh_sources

    y_true = df["human_label"].values
    y_pred = df["model_flagged"].values

    print(f"Validation sample size: {len(df)}")
    print(f"Human-labeled positive (vague) count: {y_true.sum()} ({y_true.sum()/len(df)*100:.1f}%)")
    print(f"Model-flagged positive count: {y_pred.sum()} ({y_pred.sum()/len(df)*100:.1f}%)")

    print("\n=== Classification Report ===")
    print(classification_report(y_true, y_pred, target_names=["not_vague", "vague"], digits=3, zero_division=0))

    precision, recall, f1, _ = precision_recall_fscore_support(y_true, y_pred, average="binary", zero_division=0)
    accuracy = accuracy_score(y_true, y_pred)

    print(f"Accuracy: {accuracy:.3f}")
    print(f"Precision: {precision:.3f}")
    print(f"Recall: {recall:.3f}")
    print(f"F1-Score: {f1:.3f}")

    # AUC-ROC needs at least one example of each class to be meaningful
    if len(set(y_true)) < 2:
        print("\nAUC-ROC: cannot compute — human_label has only one class present in this sample.")
    else:
        auc = roc_auc_score(y_true, y_pred)  # using binary predictions as scores, since the detector is currently binary (no continuous confidence output)
        print(f"AUC-ROC: {auc:.3f}")
        print("(Note: computed from binary flag predictions, not a continuous")
        print(" confidence score — a true ROC curve would need the detector to")
        print(" output a probability/similarity score rather than a 0/1 flag.)")

    print("\n=== Confusion Matrix ===")
    cm = confusion_matrix(y_true, y_pred)
    print(f"                 Predicted Not-Vague   Predicted Vague")
    print(f"Actual Not-Vague        {cm[0][0]:>4}                {cm[0][1]:>4}")
    print(f"Actual Vague            {cm[1][0]:>4}                {cm[1][1]:>4}")

    print("\n=== Disagreements (for manual review) ===")
    disagreements = df[df["human_label"] != df["model_flagged"]]
    for _, row in disagreements.iterrows():
        print(f"\n[{row['company_name']}] human={row['human_label']} model={row['model_flagged']} (source={row['flag_source']})")
        print(f"  {row['text'][:150]}...")


if __name__ == "__main__":
    main()
