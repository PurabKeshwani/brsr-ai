"""
XGBoost Meta-Classifier — Training + LOOCV Evaluation (Phase 3, final)

Trains XGBoost on the 5 engineered features (build_xgboost_dataset.py)
using Leave-One-Out Cross-Validation — the standard, honest evaluation
approach for a dataset this small (n=80): every sample is held out and
predicted exactly once, using a model trained on the other 79, giving
n=80 independent predictions without the high variance a single
train/test split would have on this sample size.

Compared directly against Phase D's hand-tuned rule-based classifier
(analysis.vagueness_combined.analyze_combined_vagueness) on the SAME 80
samples, for an apples-to-apples ablation: does a learned decision
boundary over these features outperform hand-set thresholds?
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    precision_recall_fscore_support,
    roc_auc_score,
)
from sklearn.model_selection import LeaveOneOut
from xgboost import XGBClassifier

from analysis.vagueness_combined import analyze_combined_vagueness

FEATURES_PATH = Path("data/validation/xgboost_features.csv")
FEATURE_COLUMNS = [
    "hedging_density", "hedging_term_count", "has_kpi",
    "semantic_sim_to_vague", "semantic_sim_to_quantified", "word_count",
]


def main():
    df = pd.read_csv(FEATURES_PATH)
    X = df[FEATURE_COLUMNS].values
    y = df["human_label"].values
    texts = df["text"].values

    print(f"Dataset: {len(df)} samples, {X.shape[1]} features")
    print(f"Class balance: {y.sum()} vague / {len(y) - y.sum()} not-vague\n")

    loo = LeaveOneOut()
    xgb_predictions = np.zeros(len(y))
    xgb_probabilities = np.zeros(len(y))

    print("Running Leave-One-Out Cross-Validation (80 folds)...")
    for train_idx, test_idx in loo.split(X):
        model = XGBClassifier(
            n_estimators=50,       # kept small — n=80 with 6 features doesn't support a large ensemble without overfitting
            max_depth=3,           # shallow trees — same rationale
            learning_rate=0.1,
            eval_metric="logloss",
            random_state=42,
        )
        model.fit(X[train_idx], y[train_idx])
        xgb_predictions[test_idx] = model.predict(X[test_idx])
        xgb_probabilities[test_idx] = model.predict_proba(X[test_idx])[:, 1]

    print("\n=== XGBoost Meta-Classifier (LOOCV) ===")
    print(classification_report(y, xgb_predictions, target_names=["not_vague", "vague"], digits=3, zero_division=0))
    xgb_precision, xgb_recall, xgb_f1, _ = precision_recall_fscore_support(y, xgb_predictions, average="binary", zero_division=0)
    xgb_auc = roc_auc_score(y, xgb_probabilities)  # uses actual probabilities, not just 0/1 — a real advantage over the rule-based system's binary flag
    print(f"Accuracy: {accuracy_score(y, xgb_predictions):.3f}")
    print(f"Precision: {xgb_precision:.3f}  Recall: {xgb_recall:.3f}  F1: {xgb_f1:.3f}  AUC-ROC: {xgb_auc:.3f}")

    # Direct comparison — same 80 samples, Phase D's hand-tuned rules
    print("\n=== Phase D Rule-Based System (for comparison, same 80 samples) ===")
    rule_predictions = np.array([
        1 if analyze_combined_vagueness(text).is_flagged_vague else 0
        for text in texts
    ])
    print(classification_report(y, rule_predictions, target_names=["not_vague", "vague"], digits=3, zero_division=0))
    rule_precision, rule_recall, rule_f1, _ = precision_recall_fscore_support(y, rule_predictions, average="binary", zero_division=0)
    rule_auc = roc_auc_score(y, rule_predictions)  # binary predictions only — rule-based system has no continuous score
    print(f"Accuracy: {accuracy_score(y, rule_predictions):.3f}")
    print(f"Precision: {rule_precision:.3f}  Recall: {rule_recall:.3f}  F1: {rule_f1:.3f}  AUC-ROC: {rule_auc:.3f}")

    print("\n=== Summary Comparison (n=80, LOOCV vs rule-based) ===")
    print(f"{'Metric':<12} {'Rule-Based':<12} {'XGBoost':<12}")
    print(f"{'Precision':<12} {rule_precision:<12.3f} {xgb_precision:<12.3f}")
    print(f"{'Recall':<12} {rule_recall:<12.3f} {xgb_recall:<12.3f}")
    print(f"{'F1':<12} {rule_f1:<12.3f} {xgb_f1:<12.3f}")
    print(f"{'AUC-ROC':<12} {rule_auc:<12.3f} {xgb_auc:<12.3f}")

    # Feature importance from a final model trained on ALL data (for
    # interpretability discussion in the paper — not used for evaluation)
    final_model = XGBClassifier(n_estimators=50, max_depth=3, learning_rate=0.1, eval_metric="logloss", random_state=42)
    final_model.fit(X, y)
    print("\n=== Feature Importances (final model, trained on all 80 samples) ===")
    for name, importance in sorted(zip(FEATURE_COLUMNS, final_model.feature_importances_), key=lambda x: -x[1]):
        print(f"  {name}: {importance:.3f}")


if __name__ == "__main__":
    main()