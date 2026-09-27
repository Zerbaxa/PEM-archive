# PEM Archive

Weekly, AI-assisted digest of pediatric emergency medicine (PEM) literature.

Every week the pipeline collects newly indexed PubMed records, screens them for
relevance to the emergency care of children, gives each included paper a
**Clinical Score** and a **Research Score**, and publishes an issue with:

- **Must-read**: top 5 by Clinical Score (minimum 5/10, at most 2 per topic)
- **Researcher's pick**: top 3 by Research Score among the rest (minimum 5/10)
- **POCUS in the PED** and **AI & LLMs in the PED**: up to 3 each
- everything else that passed screening, grouped by topic

The site also has a searchable archive, a dashboard, and a public methods page.

## Pipeline

| Step | Command | Output |
|---|---|---|
| 1. Fetch | `python -m pipeline.fetch --issue YYYY-MM-DD` | `data/candidates/<issue>.json` |
| 2. Screen and score | `python -m pipeline.score --issue YYYY-MM-DD` | `data/scored/<issue>.json` |
| 3. Select and summarize | `python -m pipeline.select --issue YYYY-MM-DD` | `data/issues/<issue>.json` |
| 4. Build site | `python -m pipeline.build` | `docs/` |

- The search query is in `config/query.txt` (tested at 94% recall against five years of listings from pemdatabase.org).
- The screening and scoring rubric, which is also the LLM prompt, is in `config/rubric.md`.
- Selection rules are the constants at the top of `pipeline/select.py`.

`score` and `select` also accept results produced elsewhere (`--import DIR`, `--summaries FILE`),
which is how the first issue was made before an API key was configured.

## LLM provider

Set `LLM_PROVIDER` to `openrouter` (default in the workflows), `anthropic`, `openai` or `gemini`,
set `LLM_MODEL`, and provide that provider's API key (`OPENROUTER_API_KEY`, `ANTHROPIC_API_KEY`,
`OPENAI_API_KEY` or `GEMINI_API_KEY`). With OpenRouter, `LLM_MODEL` is an OpenRouter model id
as listed at https://openrouter.ai/models.

`SCORE_BATCH` (default 8) sets how many records go into one request. Lower it if a small model
drops records or returns broken JSON; failed batches are retried and then scored one record at a time.

## Choosing a model: calibration

Run **Actions → Calibrate model → Run workflow** with a model id. It re-scores the 2026-09-26
candidates (422 records) and compares them with the reference scoring in `data/scored/2026-09-26.json`. It
reports inclusion sensitivity/specificity, score agreement and Must-read overlap on the run page.
Nothing is committed. Compare a few cheap models before setting `LLM_MODEL`.

Locally: `python -m pipeline.score --issue 2026-09-26 --out cal.json && python -m pipeline.compare data/scored/2026-09-26.json cal.json`

## Weekly automation

`.github/workflows/weekly.yml` runs every Friday at 21:17 UTC (Saturday morning in Korea) and commits the new issue.
It can also be started by hand from the Actions tab. Setup:

1. Settings → Secrets and variables → Actions → **Secrets**: `OPENROUTER_API_KEY` (optional: `NCBI_API_KEY`).
2. Same page → **Variables** (optional): `LLM_MODEL` to override the default OpenRouter model `deepseek/deepseek-v4-flash-0731`, and `LLM_PROVIDER` if not OpenRouter.
3. Settings → Pages: deploy from branch `main`, folder `/docs`.
   GitHub Pages needs a public repository on free plans.

## Local preview

```
python -m pipeline.build
python -m http.server -d docs 8000
```

Scores and summaries are generated from abstracts and can be wrong; the site is not medical advice.
