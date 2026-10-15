"""
Diagnostic — investigates why domain_pretrain_bert.py's training loss
(20.8+) massively exceeds the untrained-further baseline (3.377) measured
separately on the same corpus, even after ruling out learning-rate as the
cause (loss stayed ~20.8 despite a 5x LR reduction). Checks whether
padding/label-masking in the DataCollatorForLanguageModeling pipeline is
behaving correctly for this corpus (heavy padding due to max_length=256
on mostly-short sentences is a plausible, untested suspect).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import torch
from transformers import AutoTokenizer, AutoModelForMaskedLM, DataCollatorForLanguageModeling

CORPUS_PATH = Path("data/training/mlm_corpus.txt")

with open(CORPUS_PATH, encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()][:8]

tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
model = AutoModelForMaskedLM.from_pretrained("bert-base-uncased")
model.eval()

print("=== Sample text lengths (in tokens, untruncated) ===")
for line in lines:
    n_tokens = len(tokenizer.encode(line))
    print(f"  {n_tokens} tokens: {line[:70]}...")

# Reproduce the EXACT pipeline used in domain_pretrain_bert.py
encodings = tokenizer(lines, truncation=True, max_length=256, padding="max_length", return_tensors=None)
examples = [{k: v[i] for k, v in encodings.items()} for i in range(len(lines))]

collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=True, mlm_probability=0.15)
batch = collator(examples)

labels = batch["labels"]
non_masked = (labels == -100).sum().item()
masked = (labels != -100).sum().item()
total = labels.numel()

print(f"\n=== Label masking check (8 examples, max_length=256) ===")
print(f"Total label positions: {total}")
print(f"Positions with label=-100 (ignored in loss, i.e. NOT masked): {non_masked}")
print(f"Positions being predicted (masked tokens, included in loss): {masked}")
print(f"Fraction of sequence being predicted: {masked/total*100:.2f}%")
print(f"(Expected ~15% of REAL tokens, but heavily diluted if most of the")
print(f" 256-length sequence is padding — padding should be excluded")
print(f" from masking, let's confirm that's actually happening.)")

# Check specifically: are any PAD tokens marked for prediction?
pad_id = tokenizer.pad_token_id
input_ids = batch["input_ids"]
pad_positions_masked = ((input_ids == pad_id) & (labels != -100)).sum().item()
print(f"\nPAD-token positions incorrectly marked as prediction targets: {pad_positions_masked}")
print("(This should be 0 — if it's not, padding is being included in the")
print(" MLM loss, which would massively inflate loss and explain the bug.)")

with torch.no_grad():
    output = model(**{k: v for k, v in batch.items()})
print(f"\nManually computed loss on this batch: {output.loss.item():.3f}")
