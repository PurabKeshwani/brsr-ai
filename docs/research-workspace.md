# BRSR research workspace

The application now follows the results section of `paper/sections/05_results.tex` through four levels: company detail, selected peers, a complete sector and all recorded sectors. The homepage is a research dashboard. The fixed sidebar provides the explorer, comparison, time series, upload and methodology routes.

## Comparison

`/compare` supports up to eight selected companies, including the paper's seven-company sample (four highest and three lowest scores), a complete sector, or the full scored population. Reporting-period filters select the corresponding subset of latest reports; they do not reconstruct unavailable historical scores. The six visual analyses answer different questions:

1. Weighted component contributions explain the score.
2. A histogram reveals concentration and empty score bands.
3. A component heatmap exposes coverage and evidence weaknesses.
4. Specificity versus clarity distinguishes concrete evidence from clear wording.
5. Company-to-sector gaps or sector ranges show relative position and dispersion.
6. Weighted headroom indicates which components offer room for improvement.

The sector register includes counts, means, medians, ranges and sample standard deviations, matching the paper's convention. The minimum-five-peer filter can reveal smaller groups. All tables export CSV. Selected-peer evidence loading is optional and fetches actual numeric measures, periods, units, boundaries and screening counts. Absolute measures are not ranked across incompatible units or business boundaries.

## Company detail and evidence

`/company/[name]` accepts exact company names; the backend also accepts CIN. `?filing=ID` selects an actual report belonging to that company. Five tabs provide score attribution and coverage; environmental metric histories; evidence review; assurance and arithmetic checks; and a searchable, paged raw-fact register.

Evidence expands inline to the exact matched sentence, original filed paragraph, numeric facts, units, periods, dimensions and source IDs. Paragraph text is rendered as text, never injected HTML. Original XBRL links are available for HTTP sources. PDF coordinates are not stored, so no PDF page location is fabricated. Signals are screening leads rather than findings of deceptive intent. Principle and SDG tags have meaningful names and explicit coverage states.

The saved specificity and current lexical rules differ for some reports. For example, Triveni retains the paper's 63.46% specificity, while current evidence-marker rules identify 26 of 52 retained narrative pairs (50.00%). This discrepancy is explicitly displayed. The fixed paper exports are preserved; live evidence counts are not presented as a reproduction of a frozen detector run. Newly uploaded reports can compute a current-rule score separately without replacing the research exports. Unscored companies remain accessible through the explorer.

## Time series

`/time-series` uses the linked paired-report score export. It provides observed trajectories, signed weighted component attribution, company changes, report links and the complete component register. The available eight-company sample is explicitly labelled an available-case analysis. Environmental series within a single XBRL filing are shown separately, grouped by unit and dimensions. Duplicated equal values collapse into one period; conflicting values are excluded; a zero baseline does not produce an infinite percentage.

## Runtime and validation

Start the backend from the repository root:

```powershell
.venv/Scripts/python.exe -m uvicorn api.main:app --app-dir src --host 127.0.0.1 --port 8000
```

Start the frontend with `npm run dev` inside `frontend`, or use `npm run build` and `npm start` for production. Set `NEXT_PUBLIC_API_BASE` when the API runs elsewhere. The installed Next.js 16.3.1 Turbopack CSS worker crashes in this Windows environment; scripts select the supported Webpack compiler. Fonts are self-hosted with their OFL licenses, so builds do not request Google Fonts.

The API caches the saved corpus snapshot using export/database modification signatures and database counts. Assurance lookups are reused within a company request, semantic ML dependencies load only when needed, and large API responses use gzip. The frontend shares short-lived request promises, loads comparison charts separately and loads peer evidence on demand. Tables are paged. Route and request skeletons, retry errors, empty states and reduced-motion-safe entry/exit transitions are shared across routes. Desktop layouts were checked at 1440 and 1920 pixels.

Validation: the production build and TypeScript pass; 27 backend regression checks and 33 browser checks pass against the actual corpus. Browser checks cover all routes, the seven-company peer sample, reporting-period filters, historical report linkage, paragraph highlighting, fact search, CSV contents, loading/error/retry/empty states, unscored records, reduced motion and actual navigation transitions. Local QA artifacts are under `.taste-skill/workspace-qa` and `.taste-skill/compare-final` (ignored build artifacts). The frontend direction is the Framed sheet app style, seed 1839216027, with the existing brand/type retained and no redraws. The domain-specific device is score-to-source traceability rather than decorative dashboard graphics.
