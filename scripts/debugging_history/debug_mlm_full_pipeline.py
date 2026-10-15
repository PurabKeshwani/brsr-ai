"""
Diagnostic — reproduces the EXACT pipeline from domain_pretrain_bert.py
(dataset.map() tokenization, not manual per-line tokenization as in
debug_mlm_loss.py) on a small slice of the real corpus, to check whether
the bug is specific to the datasets.Dataset.map() batched-tokenization
path rather than the collator itself (which was already verified correct
in isolation).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

import torch
from datasets import Dataset
from transformers import AutoModelForMaskedLM, AutoTokenizer, DataCollatorForLanguageModeling

CORPUS_PATH = Path("data/training/mlm_corpus.txt")
MAX_LENGTH = 256

with open(CORPUS_PATH, encoding="utf-8") as f:
    lines = [line.strip() for line in f if line.strip()][:100]

print(f"Testing with {len(lines)} lines from the real corpus")

dataset = Dataset.from_dict({"text": lines})
tokenizer = AutoTokenizer.from_pretrained("bert-base-uncased")
model = AutoModelForMaskedLM.from_pretrained("bert-base-uncased")
model.eval()

def tokenize_fn(examples):
    return tokenizer(examples["text"], truncation=True, max_length=MAX_LENGTH, padding="max_length")

tokenized_dataset = dataset.map(tokenize_fn, batched=True, remove_columns=["text"])

print(f"\nSample tokenized entry keys: {list(tokenized_dataset[0].keys())}")
print(f"input_ids type: {type(tokenized_dataset[0]['input_ids'])}, length: {len(tokenized_dataset[0]['input_ids'])}")
print(f"First 10 input_ids: {tokenized_dataset[0]['input_ids'][:10]}")
print(f"attention_mask first 10: {tokenized_dataset[0]['attention_mask'][:10]}")

collator = DataCollatorForLanguageModeling(tokenizer=tokenizer, mlm=True, mlm_probability=0.15)

# Reproduce exactly how Trainer would batch this (via the collator, using
# dataset __getitem__ output directly, same as the real training loop)
batch = collator([tokenized_dataset[i] for i in range(16)])

print(f"\nBatch keys: {list(batch.keys())}")
print(f"input_ids shape: {batch['input_ids'].shape}, dtype: {batch['input_ids'].dtype}")
print(f"labels shape: {batch['labels'].shape}, dtype: {batch['labels'].dtype}")

labels = batch["labels"]
masked_count = (labels != -100).sum().item()
total = labels.numel()
print(f"Masked positions: {masked_count} / {total} ({masked_count/total*100:.2f}%)")

with torch.no_grad():
    output = model(**batch)
print(f"\nLoss on this batch (real corpus, via dataset.map() pipeline): {output.loss.item():.3f}")
print("(Expect ~2.5-3.5 if this pipeline matches the working manual test)")
