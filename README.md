# Pesquisa — Physiology Abstract Scraper

A research data pipeline that collects, deduplicates, and classifies scientific abstracts from **PubMed** and **SciELO** across multiple languages.

---

## Overview

The pipeline runs queries against two sources in parallel, extracts multilingual abstracts, deduplicates by article ID, and normalizes language labels into a clean JSONL dataset.

```
queries.py → pub_getter.py ─┬─ pubmed_fetcher.py  → PubMed API (Entrez)
                            └─ scielo_fetcher.py  → SciELO (Playwright + aiohttp)
                                      ↓
                               data/output.jsonl
                                      ↓
                            tools/classify.py
                                      ↓
                        data/output_clean.jsonl + data/report.json
```

---

## Project Structure

```
.
├── data/
│   ├── output.jsonl          # raw collected abstracts
│   ├── output_clean.jsonl    # deduplicated and classified
│   └── report.json           # run statistics
├── pubmed/
│   ├── pubmed_fetcher.py     # Entrez batch fetcher
│   └── utils.py              # abstract extraction, language normalization
├── scielo/
│   ├── scielo_fetcher.py     # Playwright + aiohttp scraper
│   ├── block_guard.py        # retry logic, block detection, headers
│   ├── cookie.py             # Playwright-based cookie refresh
│   └── utils.py              # abstract splitting, PID extraction
├── shared/
│   └── langs.py              # unified language code/name mappings
├── tools/
│   └── classify.py           # dedup + language classification
├── utils/
│   └── logger.py             # verbosity-aware logger
├── pub_getter.py             # entrypoint — runs both fetchers in parallel
├── queries.py                # loads QUERIES from .env
├── utils.py                  # checkpoint, JSONL save, hashing
├── .env                      # secrets and config (never committed)
└── .gitignore
```

---

## Setup

**Requirements**: Python 3.11+

```bash
pip install aiohttp aiofiles beautifulsoup4 biopython playwright python-dotenv tqdm lxml Brotli
playwright install chromium
```

**Configure `.env`:**

```env
ENTREZ_EMAIL=your@email.com
ENTREZ_API_KEY=your_ncbi_key        # optional — raises rate limit from 3 to 10 req/s
SCIELO_COOKIE=                      # auto-populated on first run
QUERIES=renal physiology,cardiovascular physiology,respiratory physiology
VERBOSE=0                           # set to 1 for per-page debug output
```

---

## Usage

**Run the full pipeline:**

```bash
python pub_getter.py
```

Fetches all queries from both sources in parallel, saves results to `data/output.jsonl`, and checkpoints progress so interrupted runs resume where they left off.

**Classify and deduplicate:**

```bash
python -m tools.classify
```

Reads `data/output.jsonl`, removes duplicate IDs, normalizes language labels, and writes `data/output_clean.jsonl` and `data/report.json`.

---

## Output Format

Each line in the output JSONL is one article:

```json
{
  "source": "scielo",
  "query": "renal physiology",
  "id": "S0080-62342026000100413",
  "url": "http://...",
  "title": "Impact of invasive mechanical ventilation...",
  "abstracts": {
    "portuguese": "RESUMO...",
    "spanish": "RESUMEN...",
    "english": "ABSTRACT..."
  },
  "languages": ["english", "portuguese", "spanish"],
  "multilingual": true
}
```

---

## Report Format

```json
{
  "total_raw": 10000,
  "total_after_dedup": 9200,
  "duplicates_removed": 800,
  "multilingual_entries": 3400,
  "by_source": { "scielo": 6000, "pubmed": 3200 },
  "by_language": { "english": 8500, "portuguese": 3200, "spanish": 2100 }
}
```

---

## Language Support

Abstracts are normalized to full language names (e.g. `"en"` → `"english"`, `"eng"` → `"english"`). Supported ISO 639-1 and ISO 639-2 codes cover 40+ languages across Germanic, Romance, Slavic, Semitic, East Asian, and South/Southeast Asian families.

---

## Block Handling (SciELO)

SciELO is behind Bunny CDN bot protection. The scraper handles this with:

- **Playwright** for all search pagination (real Chromium TLS fingerprint)
- **aiohttp** for individual article fetches (faster, CDN less aggressive on direct URLs)
- **Automatic cookie refresh** via Playwright when a block is detected
- **Block retry cap** of 3 attempts per page before aborting the query
- **Adaptive delay** that backs off when results look sparse

If the cookie expires between runs, it is refreshed automatically on the next execution.

---

## Checkpointing

Progress is saved after each query to a checkpoint file. Re-running the pipeline skips already-collected article IDs, so interrupted runs are safe to resume without duplicating data.

---

## Notes

- PubMed fetches up to 1000 results per query in batches of 200 via the Entrez API
- SciELO paginates until a page returns 0 results
- A free NCBI API key is recommended — get one at [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/)