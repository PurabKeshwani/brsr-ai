# GRASP: BRSR Analysis and Transparency Scoring

GRASP connects sustainability claims with information reported by Indian companies in the **Business Responsibility and Sustainability Report (BRSR)**. The research implementation combines structured report ingestion, principle classification, disclosure review, Transparency Scoring, and sector comparisons through a FastAPI backend and a Next.js dashboard.

The main input is a structured **XBRL report**, supplied as an `.xml` or `.xbrl` file. A **report** is the complete company document; a **text segment** is a selected portion of report text used for analysis.

## Features

- Search companies and inspect reported figures, reporting periods, and metric trends.
- Classify text segments under the nine BRSR principles using the recovered BERT classifier through the principle-mapping API.
- Identify vague wording using a hedging lexicon and MPNet sentence similarity.
- Review claim-versus-figure signals, internal consistency, reported assurance, and missing prior-period items.
- Inspect the four Transparency Score components and compare companies within recorded sectors.
- Compare two to five companies in the dashboard.
- Upload a structured BRSR report for ingestion and analysis.

## Workflow

| Module | Purpose |
| --- | --- |
| 1. Filing acquisition and structured storage | Parse XBRL reports and store company, report, and fact records. |
| 2. Narrative selection and weak-label construction | Select text segments and obtain labels from principle tags, concept mappings, and principle notes. |
| 3. Domain adaptation and principle classification | Adapt BERT to BRSR language and train a nine-principle classifier. |
| 4. Vagueness and filing-consistency checks | Produce language flags and numerical review records. |
| 5. Principle mapping and the zero-shot comparator | Summarise classifier probabilities and compare supervised mapping with zero-shot MPNet. |
| 6. Transparency Score and peer comparison | Calculate component scores and sector benchmarks. |
| 7. Service layer and runtime traceability | Expose analysis through the API and identify the classifier used by the mapping endpoint. |

The Transparency Score uses fixed implementation weights:

```text
Transparency Score = 0.40 × Completeness
                   + 0.30 × Specificity
                   + 0.20 × Clarity
                   + 0.10 × Mapped SDG coverage
```

**Clarity reuses the vagueness detector:** it is the percentage of scoring text segments without a vagueness flag. Claim-versus-figure and assurance flags remain separate review outputs. Principle probabilities describe model support for a principle assignment, rather than a regulatory compliance decision.

## Audited results

Final values and evaluation conditions are recorded in the [consolidated audit](results/audit/stage1_7_final_master_table.md). The single-label dataset contains **42,409 text segments**. The saved company-score snapshot contains **1,164 companies across 72 sectors**, with 47 sectors containing at least five companies. These are saved research snapshots; a fresh clone does not include the populated database.

| Evaluation | Result | Population / interpretation |
| --- | --- | --- |
| Recovered BERT Top-1 agreement | **93.00%**, 95% CI **92.04–93.89%** | 6,201 test text segments from 175 companies excluded from supervised training. |
| Recovered BERT Top-2 agreement | **97.68%**, 95% CI **97.10–98.21%** | Same test group; the reference label appears among the two highest-ranked principles. |
| Recovered BERT macro-F1 | **0.9158**, 95% CI **0.9036–0.9277** | Same test group; each principle receives equal weight. |
| Top-1 agreement by label source | Section B **63.35%**; Section C **95.15%**; principle notes **90.72%** | 352 / 5,364 / 485 text segments respectively. |
| Frozen language detector | **F1 = 0.7436** | 80 development text segments. |
| Language detector versus AI labels | **F1 = 0.6885** | 70 text segments; exploratory comparison with one AI annotation set. |
| Supervised versus zero-shot mapping | **93.00% versus 67.63%** Top-1 | Same 6,201 text segments; the supervised value reuses the classifier evaluation. |
| Transparency Score versus historical human ratings | **Pearson r = 0.6314**, 95% CI **0.2683–0.8519** | 20 company ratings; rater blinding is not documented. |

Classification results measure agreement with taxonomy-derived **weak labels**, including AI-assisted mappings. Company separation applies to supervised fine-tuning; checkpoint-specific membership of the earlier language-adaptation corpus is not verified. Detector metrics cover the language branch, rather than the complete numerical auditor. Full intervals and diagnostic comparisons are available in [results/audit](results/audit/).

## Technology

| Layer | Main tools |
| --- | --- |
| Backend | Python, FastAPI, Pydantic, SQLAlchemy, SQLite |
| Language analysis | PyTorch, Transformers, Sentence Transformers, BERT, MPNet |
| Frontend | Next.js 16.3.1, React 19.2.8, TypeScript, Tailwind CSS, Recharts |
| Research manuscript | LaTeX, with sources in [paper/](paper/) |

## Run locally

The following commands use **Windows PowerShell**. Run backend commands from the repository root and use **`.venv-ml`** for Python work.

### 1. Install dependencies

Requirements:

- Python 3.13 for the current ML environment.
- Node.js **20.9 or later** and npm for the frontend.
- Internet access for package installation and the first MPNet model download, unless the model is already cached.

Reuse the existing `.venv-ml` environment when available. For a fresh checkout, create it first:

```powershell
py -3.13 -m venv .venv-ml
```

Install Python dependencies using that environment directly:

```powershell
& ".\.venv-ml\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv-ml\Scripts\python.exe" -m pip install -r requirements.txt
& ".\.venv-ml\Scripts\python.exe" -m pip install pandas requests python-multipart
```

The final command installs direct API dependencies that are not explicitly listed in the current `requirements.txt`. `python-multipart` supports file uploads. The main XBRL workflow does not require Java or PDF/OCR extraction; the PDF tooling retained in `requirements.txt` belongs to the earlier extraction workflow.

### 2. Prepare local data and model assets

The `data/` directory is ignored by Git. Restore the required assets from the existing research workspace, or ingest valid BRSR reports to populate a new database.

| Local asset | Used for |
| --- | --- |
| `data/brsr.db` | Populated company and report database. A new, empty database is created automatically if absent. |
| `data/models/brsr_company_split_classifier/seed_99/recovered_checkpoint_7460/` | Tokenizer and recovered classifier weights for `/compliance-mapping`. |
| `data/analysis/sector_benchmarks.csv` | Saved peer comparisons used by `/sector-benchmark`. |
| `data/analysis/transparency_scores.csv` | Input to the peer-benchmark generation script. |

The principle-mapping endpoint returns **503** if the recovered checkpoint is unavailable. The sector-benchmark endpoint returns **503** if the benchmark CSV is absent. Other routes can be used with the assets relevant to those routes. The classifier loader uses CUDA when available and otherwise uses the CPU.

### 3. Start the backend

From the repository root:

```powershell
& ".\.venv-ml\Scripts\python.exe" -m uvicorn api.main:app --reload --app-dir src
```

- API: [http://127.0.0.1:8000](http://127.0.0.1:8000)
- Health endpoint: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive API documentation: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

### 4. Start the frontend

Open a second terminal at the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The frontend calls `http://127.0.0.1:8000` by default. Run npm commands inside `frontend/`; the root `package.json` does not contain the dashboard start scripts.

For a different backend address, create `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

Restart the frontend after changing this value. Further frontend details are in [frontend/README.md](frontend/README.md).

### Configuration

| Variable | Where to set it | Default |
| --- | --- | --- |
| `BRSR_DB_URL` | Backend process environment, before startup | SQLite at `data/brsr.db`. |
| `NEXT_PUBLIC_API_BASE` | `frontend/.env.local` or the frontend process environment | `http://127.0.0.1:8000`. |

The backend entry point reads `BRSR_DB_URL` from the process environment; it does not automatically load a root `.env` file. For example, select a different database in the backend terminal before starting Uvicorn:

```powershell
$env:BRSR_DB_URL = "sqlite:///D:/path/to/brsr.db"
```

## Ingest reports and build benchmarks

The dashboard upload page accepts **`.xml` and `.xbrl`** files. PDF uploads are not supported by the current analysis API.

For ingestion from a URL, use the single-company script from the repository root. Replace both example arguments with a company name and a valid BRSR XBRL URL:

```powershell
& ".\.venv-ml\Scripts\python.exe" "scripts\01_ingestion\ingest_company.py" "Company name" "https://example.com/company-brsr.xml"
```

For bulk ingestion, [bulk_ingest.py](scripts/01_ingestion/bulk_ingest.py) reads a filings CSV containing company and XBRL URL columns and maintains a progress log.

When `data/analysis/transparency_scores.csv` and company industry codes are available, generate sector benchmarks with:

```powershell
& ".\.venv-ml\Scripts\python.exe" "scripts\06_transparency_score\build_peer_benchmarks.py"
```

## API routes

Use the company name returned by `GET /companies`. URL-encode names containing spaces or special characters.

| Method | Route | Purpose |
| --- | --- | --- |
| GET | `/health` | API health. |
| GET | `/companies` | List stored companies. |
| GET | `/companies/{name}/filings` | List a company's reports. |
| GET | `/companies/{name}/report` | Trends, consistency, assurance, claim signals, and missing items for the latest report. |
| GET | `/companies/{name}/transparency-score` | Four score components and the combined score. |
| GET | `/companies/{name}/truth-audit` | Language and numerical review summaries. |
| GET | `/companies/{name}/sector-benchmark` | Saved comparison with sector peers. |
| GET | `/companies/{name}/compliance-mapping` | Recovered classifier probabilities, method name, and model path. |
| GET | `/companies/compare?names=CompanyA,CompanyB` | Compare two to five companies. |
| POST | `/companies/ingest` | Ingest a report URL using JSON fields `company_hint` and `xbrl_url`. |
| POST | `/companies/upload-and-analyze` | Upload an `.xml` or `.xbrl` file using multipart field `file`. |

The mapping API reports method `recovered_seed99_supervised_classifier`. The current dashboard uses report, score, audit, comparison, and benchmark routes; principle mapping is also available directly through the API.

## Repository layout

```text
frontend/           Next.js dashboard, API client, and UI components
src/api/            FastAPI routes and response schemas
src/db/             Database models and session management
src/ingestion/      XBRL parsing and ingestion
src/analysis/       Trends, review checks, principle mapping, and scoring
scripts/            Numbered ingestion, training, analysis, and reporting scripts
results/audit/      Approved result summaries and evaluation artifacts
results/improve/    Separate improvement experiments and development records
paper/              LaTeX manuscript, figures, supplementary tables, and revision records
docs/               Development notes and module documentation
tests/              Existing tests and fixtures
data/               Local reports, database, model weights, and generated analysis; ignored by Git
```

## Documentation and research records

- [Consolidated audited results](results/audit/stage1_7_final_master_table.md)
- [Research manuscript](paper/main.tex)
- [Manuscript evidence manifest](paper/revision/evidence_manifest.json)
- [Frontend setup and routes](frontend/README.md)
- [Development documentation](docs/)

Development notes retain earlier experiments and historical values. The consolidated audit takes precedence for the final reported metrics. Running the dashboard with existing assets does not require retraining the models or rerunning the evaluation scripts.
