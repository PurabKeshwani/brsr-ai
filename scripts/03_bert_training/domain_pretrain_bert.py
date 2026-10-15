"""
Domain-Adaptive Pretraining — MLM Training (Phase: Domain Pretraining, Step 2)

Continues pretraining bert-base-uncased with Masked Language Modeling on
the BRSR narrative-text corpus built by build_mlm_corpus.py, before the
supervised 9-principle fine-tuning (scripts/train_bert_classifier.py) is
run again on top of this domain-adapted checkpoint.

Rationale: bert-base-uncased's original pretraining (Wikipedia +
BooksCorpus) has no exposure to ESG/BRSR-specific vocabulary and phrasing
("Scope 1 emissions", "materiality assessment", "NGRBC", "greenwashing"
domain terms, formal Indian-regulatory-filing register). Continued MLM
pretraining on in-domain text is a standard, well-established technique
(domain-adaptive pretraining, e.g. as used by ESG-BERT and similar
domain-adapted models) to give the encoder better-suited internal
representations before task-specific fine-tuning, without needing any
labels for this stage.

Honest scope note: this is 1-2 epochs of continued pretraining on a
~4.6M-word corpus on a single 4GB-VRAM consumer GPU — not the scale of
pretraining used for models like ESG-BERT (which used much larger corpora
and more compute). This is disclosed as a lightweight domain-adaptation
step, not a claim of full-scale domain pretraining.
"""
from __future__ import annotations

from pathlib import Path

import torch
from datasets import Dataset
from transformers import (
    AutoModelForMaskedLM,
    AutoTokenizer,
    DataCollatorForLanguageModeling,
    Trainer,
    TrainingArguments,
)

CORPUS_PATH = Path("data/training/mlm_corpus.txt")
OUTPUT_DIR = Path("data/models/domain_adapted_bert")
BASE_MODEL = "bert-base-uncased"

MAX_LENGTH = 256  # shorter than the 512 used for classification — MLM benefits less from very long sequences, and this keeps memory usage down on 4GB VRAM
BATCH_SIZE = 4
GRAD_ACCUMULATION_STEPS = 8  # effective batch size 32
NUM_EPOCHS = 2
# Reduced from 5e-5 after a real failure was caught by evidence-checking:
# training loss started at 20.34 and only fell to 10.89 (never beating
# the untrained bert-base-uncased baseline of 3.377 on the same corpus,
# measured separately) — the model was catastrophically forgetting its
# pretrained knowledge rather than adapting it. 5e-5 is a fine-tuning-
# scale learning rate; continued MLM pretraining on top of already-good
# pretrained weights needs to be much gentler.
LEARNING_RATE = 1e-5
MLM_PROBABILITY = 0.15  # standard BERT masking rate


def main():
    print(f"CUDA available: {torch.cuda.is_available()}")
    if torch.cuda.is_available():
        print(f"GPU: {torch.cuda.get_device_name(0)}")

    print(f"Loading corpus from {CORPUS_PATH}...")
    with open(CORPUS_PATH, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]
    print(f"Loaded {len(lines)} text segments")

    dataset = Dataset.from_dict({"text": lines})

    tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL)
    model = AutoModelForMaskedLM.from_pretrained(BASE_MODEL)


    def tokenize_fn(examples):
        return tokenizer(examples["text"], truncation=True, max_length=MAX_LENGTH, padding="max_length")

    print("Tokenizing corpus...")
    tokenized_dataset = dataset.map(tokenize_fn, batched=True, remove_columns=["text"])

    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer, mlm=True, mlm_probability=MLM_PROBABILITY,
    )

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR / "checkpoints"),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRAD_ACCUMULATION_STEPS,
        learning_rate=LEARNING_RATE,
        warmup_steps=0.1,
        logging_steps=50,
        # NOTE: with gradient_accumulation_steps=8, the loss value printed
        # in each {'loss': ...} log line is the SUM across the 8
        # accumulated micro-batches, not the average — divide by 8 to get
        # the true per-batch loss (confirmed via a real, isolated
        # pipeline test that verified the training pipeline itself is
        # correct and produces loss ~2.0-3.5 on real corpus data; the
        # same display behavior was independently found earlier in this
        # project during BERT classifier fine-tuning).
        save_strategy="epoch",
        fp16=torch.cuda.is_available(),  # re-enabled: the earlier instability (loss ~20+) was root-caused to a stale/corrupted checkpoint being silently resumed (see git history), not to mixed precision — disabling fp16 only cost 8x training time (9h vs ~1h) without addressing the real bug. Safe to re-enable now that the checkpoint directory is confirmed clean.
        max_grad_norm=1.0,  # standard gradient clipping — added as a genuine extra safety margin against instability, at negligible cost, now that we're back on fp16  # disabled after the LR-related failure — testing without mixed-precision first to isolate variables, matching an approach used earlier in this project for the same class of instability
        report_to="none",
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
        data_collator=data_collator,
    )

    print("\nMeasuring pre-training baseline loss (sanity check before committing to a full run)...")
    eval_batch = data_collator([tokenized_dataset[i] for i in range(min(50, len(tokenized_dataset)))])
    model.eval()
    with torch.no_grad():
        baseline_output = model(**{k: v.to(model.device) for k, v in eval_batch.items()})
    print(f"Baseline loss on {min(50, len(tokenized_dataset))} samples: {baseline_output.loss.item():.3f}")
    print("(Expect this to be close to the untrained-further baseline measured earlier: ~3.38)")
    model.train()

    print("\nStarting domain-adaptive pretraining...")
    trainer.train()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    trainer.save_model(str(OUTPUT_DIR / "final_model"))
    tokenizer.save_pretrained(str(OUTPUT_DIR / "final_model"))
    print(f"\nDomain-adapted model saved to {OUTPUT_DIR / 'final_model'}")


if __name__ == "__main__":
    main()
