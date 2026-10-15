# Phase 3: BERT Principle Classification (with Domain-Adaptive Pretraining)

## What this phase does

This phase builds a 9-class text classifier that predicts which BRSR
principle (P1-P9) a piece of narrative disclosure text addresses, using
a fine-tuned BERT model. It has two stages: (1) domain-adaptive
pretraining, where `bert-base-uncased` is continued-pretrained on
unlabeled BRSR/ESG text to adapt its internal representations to this
domain's vocabulary before any classification training happens, and
(2) supervised fine-tuning, where a classification head is trained on
the weak-supervision-labeled dataset from Phase 2.

Core files:

- `scripts/03_bert_training/build_training_dataset.py` — builds the
  final labeled train/val/test CSVs from the database, applying the
  deduplication fix described in Phase 2
- `scripts/03_bert_training/build_mlm_corpus.py` — extracts the full
  unlabeled narrative-text corpus (all companies, no label needed) for
  domain pretraining
- `scripts/03_bert_training/domain_pretrain_bert.py` — continues
  pretraining BERT with Masked Language Modeling on the BRSR corpus
- `scripts/03_bert_training/train_bert_classifier.py` — fine-tunes the
  (domain-adapted) BERT model on the labeled 9-principle dataset

## Why this approach (not alternatives)

**Domain-adaptive pretraining vs. fine-tuning vanilla BERT directly.**
`bert-base-uncased` is pretrained on Wikipedia and BooksCorpus — general
English text with no exposure to ESG/regulatory vocabulary ("Scope 1
emissions", "materiality assessment", "NGRBC", formal Indian-regulatory
filing register). The alternative — skipping domain pretraining and
fine-tuning vanilla BERT directly on the labeled dataset — was tried
first, as the simpler baseline. Domain-adaptive pretraining was added
afterward specifically to test whether adapting BERT's encoder to this
vocabulary _before_ task-specific training would improve results, matching
a well-established technique in domain-specific NLP (the same general
approach used by domain-adapted models like ESG-BERT, though at a much
smaller scale here — disclosed honestly as "1-2 epochs on ~4.6M words on
a single consumer GPU," not a claim of matching full-scale domain
pretraining).

**Result: it worked, measurably.** F1 improved from 0.6186 (vanilla
BERT) to 0.6584 (domain-adapted BERT) on the identical labeled dataset —
a real, reproducible improvement, not assumed.

## Key decisions and trade-offs

**Decision: scale up training data iteratively and measure the effect at
each step**, rather than jumping straight to the full dataset. F1 was
tracked across four dataset sizes: 284 samples (F1=0.11) → 546 samples
(F1=0.20) → 4,854 samples with vanilla BERT (F1=0.62) → 4,854 samples
with domain-adapted BERT (F1=0.66). This progression is itself evidence
that the pipeline was learning a genuine signal, not overfitting noise
— performance scaled predictably with data volume before the domain-
adaptation improvement was layered on top.

**Trade-off accepted: F1=0.66 is below the report's originally stated
target of F1=0.82.** The 0.82 figure (from an earlier draft of the
project's planning documents) assumed 12,340 manually-annotated segments
with expert double-annotation — a scale and labeling method this project
does not have. Rather than reporting an unverifiable number, the actual
achieved result is reported honestly, alongside the full evidence trail
of what was tried and why it improved.

**Decision: use a small, GPU-memory-conscious training configuration**
(batch size 4, gradient accumulation to reach an effective batch size of
16-32, mixed precision where stable) because training ran on a single
consumer GPU (RTX 2050, 4GB VRAM) — not the 8GB+ CUDA GPU environment
assumed in early planning documents. This constraint shaped multiple
downstream debugging decisions (see below).

## Real bugs found and fixed here

This phase had the highest concentration of real, evidence-diagnosed
bugs in the entire project — several are worth understanding in detail
because each one could easily have gone unnoticed and silently produced
a misleading result.

1. **Environment/dependency chain bugs (before any model code ran).**
   `transformers` v5.15.0 (a very recent release) had removed several
   `TrainingArguments` parameters used in initial scripts —
   `warmup_ratio` (merged into `warmup_steps`, now accepting a float as
   a ratio) and `overwrite_output_dir` (removed entirely, requiring an
   explicit manual directory wipe instead). Both were only discovered by
   reading the actual `TypeError` messages and searching for the current
   API rather than assuming familiar parameter names still worked.

2. **CUDA/PyTorch install index mismatch.** The `cu121` PyTorch wheel
   index returned "no version found" — traced to PyTorch having moved
   its actively-maintained CUDA wheel indexes forward (cu124/cu126/cu128)
   since `cu121` was last current. Fixed by checking the GPU driver's
   actual supported CUDA version via `nvidia-smi` and selecting a
   matching, currently-published index — not by guessing at index names.

3. **`sentence-transformers` crashed with `STATUS_HEAP_CORRUPTION`
   (Windows exit code -1073740940) on import — no Python traceback at
   all.** This was isolated systematically: testing `import torch` alone
   (passed), then `import sentence_transformers` alone (crashed, same
   exit code) — narrowing the failure to that specific import before any
   model loading occurred. Root cause: the same Python virtual
   environment also had leftover packages from earlier, abandoned
   PDF/OCR experimentation (`opencv-python` _and_ `opencv-python-headless`
   installed simultaneously — a known source of native DLL conflicts on
   Windows). Fixed by creating a fresh, minimal virtual environment
   rather than trying to selectively uninstall conflicting packages from
   the contaminated one.

4. **A misleading "loss ~8.9 instead of ~2.2" result — turned out to be a
   display quirk, not a bug.** Early classifier training runs logged a
   loss around 8.8-8.9, roughly 4x the expected ~2.2 baseline for 9-class
   cross-entropy at random-guessing. Initial hypotheses (label dtype
   issue, wrong loss function, corrupted data) were each tested directly
   against the data and ruled out one at a time. The actual explanation:
   with `gradient_accumulation_steps=4`, the transformers Trainer's
   logged loss is the _summed_ loss across the 4 accumulated
   micro-batches, not the average — `8.8 / 4 = 2.2`, exactly matching
   the expected baseline. This was confirmed by manually reproducing the
   exact training pipeline (tokenization, collation, and a forward pass)
   on a small slice of real data outside the Trainer loop, which returned
   a clean loss of ~2.0-2.1, proving the underlying computation was
   correct and only the logged number's scale was misleading.

5. **Domain-adaptive pretraining initially failed catastrophically
   (loss started at 20.34, never dropped below ~11).** This was
   confirmed as a genuine failure — not a display artifact — by
   independently measuring the untrained-further baseline MLM loss on
   the same corpus (~3.377, using a fresh, un-adapted BERT model),
   which the training run never beat even after two full epochs. Two
   separate root causes were investigated and resolved in sequence:
   - First hypothesis (learning rate too aggressive for continued
     pretraining, `5e-5` being fine-tuning-scale rather than gentle
     continued-pretraining-scale) was tested by reducing the learning
     rate 5x — this did not fix it, ruling out that hypothesis.
   - Actual root cause: a **stale/corrupted checkpoint directory from an
     earlier failed run was being silently auto-resumed** by the
     Trainer, because `transformers` v5 no longer has a working
     `overwrite_output_dir` parameter to prevent this. Confirmed by
     directly inspecting the checkpoint directory and finding leftover
     `checkpoint-1591`/`checkpoint-3182` folders from the earlier failed
     run, with timestamps matching that run exactly. Fixed by explicitly
     deleting the checkpoint directory before each training run and
     passing `resume_from_checkpoint=False` to `trainer.train()` as a
     second, explicit safeguard against ever silently resuming stale
     state again.

6. **After the checkpoint fix, loss appeared to still start at ~20 —
   this turned out to be the same summed-vs-averaged display quirk from
   bug #4, reapplied to a different training run.** Dividing the logged
   values by the gradient-accumulation factor (8, for this run)
   recovered the expected ~2.5-3.4 baseline range, and the values
   genuinely decreased over training (down to ~1.6-1.7 by the end) —
   confirming the domain-adaptive pretraining was working correctly the
   whole time, and the earlier "failure" fear was itself a
   misinterpretation of the same logging behavior already understood
   from bug #4, just not immediately recognized in this different
   script.

## Your personal reflection (fill this in yourself)

_[This section is intentionally left for you to write in your own words.
Some starting questions to reflect on, based on the actual decisions
above:]_

- Bug #4 (the loss-display quirk) and bug #6 are essentially the same
  misunderstanding happening twice, in two different scripts. What would
  you personally do differently to make sure a fix like this, once
  understood, doesn't need to be independently re-discovered later?
- The environment/dependency bugs (#1, #2, #3) took real time to resolve
  and had nothing to do with the actual ML methodology. Do you think
  this kind of infrastructure debugging is a fair thing to document as
  part of the project's technical contribution, or is it just "noise"
  around the real work? Why?
- Domain-adaptive pretraining gave a real but fairly modest F1
  improvement (0.6186 → 0.6584). Given how much debugging time it
  required, do you think it was worth including in the final pipeline?
  What would you say if a mentor asked "was this worth it"?
- The F1 target of 0.82 from the original plan was never reached. How do
  you personally think about that gap — as a shortfall, or as an honest
  finding given the very different data/labeling approach actually used?
