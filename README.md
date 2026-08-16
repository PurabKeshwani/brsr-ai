# AI-Powered BRSR Analysis & Greenwashing Detection

Production-grade, research-level system for automated analysis of SEBI BRSR sustainability
disclosures — principle classification, greenwashing/claim-contradiction detection,
composite Transparency Scoring, and longitudinal peer benchmarking.

See `paper/` (once populated) and the project plan doc shared alongside this repo for full
context, novelty positioning, and the phase-by-phase roadmap.

## Status

| Phase | Status |
|---|---|
| 0 — Repo scaffolding | ✅ Done |
| 1 — Ingestion pipeline (OpenDataLoader) | 🔶 In progress — verified on synthetic PDF, needs real BRSR filings next |
| 2 — Annotation & corpus scaling | ⬜ Not started |
| 3 — Classifier training | ⬜ Not started |
| 4 — Claim-evidence contradiction module | ⬜ Not started |
| 5 — Temporal drift / benchmarking | ⬜ Not started |
| 6 — Transparency scoring | ⬜ Not started |
| 7 — Backend API | ⬜ Not started |
| 8 — Frontend dashboard | ⬜ Not started |
| 9 — Productionization | ⬜ Not started |

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

OpenDataLoader PDF wraps a Java CLI — you need a JRE (Java 17+) available on PATH. If you
don't have one: `sudo apt install openjdk-21-jre-headless` (Linux) or install a JDK/JRE
manually on Windows/Mac.

## Running the ingestion pipeline

```bash
# regenerate the synthetic smoke-test fixture (only needed once, or after editing it)
python3 tests/fixtures/make_synthetic_brsr_pdf.py

# run it through the real extractor
python3 -c "
import sys; sys.path.insert(0, 'src')
from ingestion.extractor import extract
res = extract('tests/fixtures/synthetic_brsr_sample.pdf', 'data/extracted')
print(res.markdown_text)
"
```

To run against a **real** BRSR PDF, drop it in `data/raw_pdfs/` and point `extract()` at it
instead — no code changes needed for a standard digital PDF. Scanned filings need the hybrid
OCR backend (`extract(..., hybrid=True)`), which isn't wired up to a running server yet —
next thing to test once we have an actual scanned filing to validate against.

## Tests

```bash
pytest tests/ -v
```

## Repository layout

See `infra/`, `src/`, `tests/`, `notebooks/` — structure and rationale documented in the
project plan. Short version: everything importable lives in `src/`, notebooks (Colab/Kaggle)
import from `src/` rather than duplicating logic in cells, so training code stays identical
across local/Colab/Kaggle environments.
