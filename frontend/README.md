# GRASP Dashboard

The GRASP dashboard provides a browser interface for company BRSR report analysis. The frontend uses **Next.js 16.3.1**, **React 19.2.8**, TypeScript, Tailwind CSS, and Recharts. Analysis and model inference run in the Python backend.

## Pages

| Route | Purpose |
| --- | --- |
| `/` | Landing page and company search. |
| `/companies` | Browse stored companies. |
| `/company/[name]` | Company report, Transparency Score, metric trends, and review records. |
| `/compare` | Compare two to five companies. |
| `/upload` | Upload a structured BRSR report in `.xml` or `.xbrl` format. |

A report is the complete company document. A text segment is a selected portion of report text used for language analysis. The score breakdown shows Completeness, Specificity, Clarity, and mapped SDG coverage. Clarity uses vagueness flags and contributes 20% of the total score.

## Prerequisites

- Node.js **20.9 or later** and npm.
- The FastAPI backend running at `http://127.0.0.1:8000`, or another configured address.
- Company reports in the backend database for existing-company views.
- `data/analysis/sector_benchmarks.csv` in the backend workspace for peer comparisons.

Backend setup, local data requirements, and audited results are documented in the [root README](../README.md).

## Run locally

From the repository root:

```powershell
Set-Location frontend
npm ci
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). Keep the backend running in a separate terminal. The `dev`, `build`, and `start` scripts belong to this directory, not the repository root.

## Backend address

The API client in [src/lib/api.ts](src/lib/api.ts) reads `NEXT_PUBLIC_API_BASE`. The default is `http://127.0.0.1:8000`.

For a different backend address, create `.env.local` inside `frontend/`, alongside `package.json`:

```dotenv
NEXT_PUBLIC_API_BASE=http://127.0.0.1:8000
```

Restart the development server after changes. Next.js includes `NEXT_PUBLIC_` values in the browser bundle at build time, so set the backend address before creating a production build.

## Available commands

Run these commands inside `frontend/`:

| Command | Purpose |
| --- | --- |
| `npm ci` | Install dependencies from the committed lockfile. |
| `npm run dev` | Start the development server. |
| `npm run build` | Create a production build. |
| `npm run start` | Serve an existing production build. |

## Structure

```text
src/app/                  App Router pages, layouts, and loading states
src/components/           Search, company views, and shared components
src/components/report/    Score, trend, assurance, and audit sections
src/components/ui/        Shared visual components
src/lib/api.ts            API requests and response types
src/lib/utils.ts          Shared utilities
public/                   Static assets
```

The API types are maintained alongside the backend schemas in [src/api/schemas.py](../src/api/schemas.py). Backend response changes should be reflected in the frontend client and consuming components.

## Common setup issues

- **No companies appear:** a fresh clone does not contain `data/brsr.db`. Restore a populated database or ingest a valid BRSR report through the upload page or backend.
- **Requests fail:** confirm the backend address and check [the health endpoint](http://127.0.0.1:8000/health).
- **Sector benchmark unavailable:** restore or generate `data/analysis/sector_benchmarks.csv`; the backend returns 503 when this file is absent.
- **Upload rejected:** the analysis API accepts `.xml` and `.xbrl`, rather than PDF files.
- **First analysis is slow:** semantic analysis can download and initialise MPNet on first use. Later requests in the same backend process reuse the loaded model.

The frontend is part of the main repository and is tracked as a regular directory.
