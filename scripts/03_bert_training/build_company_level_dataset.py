"""
Stage 2 & 3: Strict Company-Level Split (Zero Company Overlap)
--------------------------------------------------------------
Splits all current clean BRSR training segments by company (CIN)
using GroupShuffleSplit, guaranteeing that:
1. NO company in the test set has ever been seen in the training or validation sets.
2. Evaluates out-of-sample generalization to completely unseen corporate entities.
"""

from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import GroupShuffleSplit

DATA_DIR = Path("data/training")
OUTPUT_DIR = Path("data/training_company_split")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_SEED = 42


def main():
    print("=================================================================")
    print("  BUILDING STRICT COMPANY-LEVEL SPLIT (GroupShuffleSplit by CIN)")
    print("=================================================================")

    # Combine existing clean splits to get the complete current corpus
    train_orig = pd.read_csv(DATA_DIR / "train.csv")
    val_orig = pd.read_csv(DATA_DIR / "val.csv")
    test_orig = pd.read_csv(DATA_DIR / "test.csv")

    all_data = pd.concat([train_orig, val_orig, test_orig], ignore_index=True)
    print(f"Total corpus: {len(all_data)} segments across {all_data['cin'].nunique()} unique companies (CINs).")

    # Step 1: Split into Train (70% companies) and Temp (30% companies)
    gss_train = GroupShuffleSplit(n_splits=1, train_size=0.70, random_state=RANDOM_SEED)
    train_idx, temp_idx = next(gss_train.split(all_data, groups=all_data["cin"]))

    train_data = all_data.iloc[train_idx].reset_index(drop=True)
    temp_data = all_data.iloc[temp_idx].reset_index(drop=True)

    # Step 2: Split Temp into Validation (15% companies) and Test (15% companies)
    gss_val_test = GroupShuffleSplit(n_splits=1, train_size=0.50, random_state=RANDOM_SEED)
    val_sub_idx, test_sub_idx = next(gss_val_test.split(temp_data, groups=temp_data["cin"]))

    val_data = temp_data.iloc[val_sub_idx].reset_index(drop=True)
    test_data = temp_data.iloc[test_sub_idx].reset_index(drop=True)

    # Verification checks
    train_cins = set(train_data["cin"])
    val_cins = set(val_data["cin"])
    test_cins = set(test_data["cin"])

    print("\n--- COMPANY OVERLAP VERIFICATION ---")
    print(f"Train companies: {len(train_cins)} (Segments: {len(train_data)})")
    print(f"Val companies:   {len(val_cins)} (Segments: {len(val_data)})")
    print(f"Test companies:  {len(test_cins)} (Segments: {len(test_data)})")

    overlap_train_test = train_cins.intersection(test_cins)
    overlap_train_val = train_cins.intersection(val_cins)
    overlap_val_test = val_cins.intersection(test_cins)

    print(f"Company overlap (Train vs Test): {len(overlap_train_test)} -> {'[PASS] STRICT 0%' if len(overlap_train_test)==0 else '[FAIL]'}")
    print(f"Company overlap (Train vs Val):  {len(overlap_train_val)} -> {'[PASS] STRICT 0%' if len(overlap_train_val)==0 else '[FAIL]'}")
    print(f"Company overlap (Val vs Test):   {len(overlap_val_test)} -> {'[PASS] STRICT 0%' if len(overlap_val_test)==0 else '[FAIL]'}")

    # Check text overlap across company-split (only cross-company boilerplate can overlap now)
    train_texts = set(train_data["text"])
    test_texts = set(test_data["text"])
    text_overlap = train_texts.intersection(test_texts)
    print(f"Cross-company exact boilerplate overlap: {len(text_overlap)} / {len(test_data)} ({len(text_overlap)/len(test_data)*100:.2f}%)")

    # Check class balance across the 9 principles
    print("\n--- PER-PRINCIPLE CLASS BALANCE ---")
    p_train = train_data["principle_id"].value_counts(normalize=True).sort_index()
    p_test = test_data["principle_id"].value_counts(normalize=True).sort_index()
    for p in sorted(p_train.index):
        print(f"  {p:<18}: Train={p_train[p]*100:>5.2f}% | Test={p_test.get(p, 0)*100:>5.2f}%")

    # Save to dedicated directory
    train_data.to_csv(OUTPUT_DIR / "train.csv", index=False)
    val_data.to_csv(OUTPUT_DIR / "val.csv", index=False)
    test_data.to_csv(OUTPUT_DIR / "test.csv", index=False)
    print(f"\nSaved strict company-level split to: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
