# AbExtractor

![Python](https://img.shields.io/badge/python-3.11%2B-blue)
![License](https://img.shields.io/badge/license-unlicensed-lightgrey)
![Status](https://img.shields.io/badge/status-active-success)
![Sources](https://img.shields.io/badge/sources-PubMed%20%7C%20ArXiv%20%7C%20SciELO-orange)
![Dataset](https://img.shields.io/badge/output-JSONL%20%7C%20CSV-informational)
![Async](https://img.shields.io/badge/pipeline-async%20parallel-purple)
![Playwright](https://img.shields.io/badge/browser-playwright-green)

> Multilingual scientific abstract collection, normalization, deduplication, and classification pipeline for PubMed, ArXiv, and SciELO.

Pesquisa is a high-throughput research data pipeline focused on building structured datasets from scientific literature sources. The project fetches abstracts from multiple providers in parallel, normalizes multilingual metadata, deduplicates entries, classifies content by query/topic, and exports clean datasets for downstream NLP, ML, and academic analysis workflows.

---

## Features

- Parallel fetching from multiple scientific sources
- PubMed integration through the Entrez API
- ArXiv integration with batched API collection
- SciELO scraping with anti-block handling
- Automatic retry and adaptive backoff mechanisms
- Checkpoint-based resumable execution
- Multilingual abstract extraction and normalization
- Language detection and canonical mapping
- Deduplication by article identifier
- Query-based dataset classification
- JSONL-first pipeline for large-scale processing
- CSV export utilities
- Built for large dataset generation workflows

---

## Supported Sources

| Source | Method | Notes |
|---|---|---|
| PubMed | Entrez API | High-volume biomedical abstract collection |
| ArXiv | API | Scientific preprints and technical papers |
| SciELO | Playwright + aiohttp | Handles multilingual Latin American journals |

---

## Project Architecture

```text
.env
  ↓
fetch.py
  ├── pubmed/fetcher.py
  ├── arxiv_local/fetcher.py
  └── scielo/fetcher.py
          ↓
  data/dataset_raw.jsonl
          ↓
classify.py
          ↓
  data/classified/
  data/report.json
```

---

## Repository Structure

```text
.
├── data/
│   ├── dataset_raw.jsonl
│   ├── dataset_clean.jsonl
│   ├── classified/
│   └── report.json
│
├── pubmed/
│   ├── fetcher.py
│   └── utils.py
│
├── arxiv_local/
│   └── fetcher.py
│
├── scielo/
│   ├── fetcher.py
│   ├── block_guard.py
│   ├── cookie.py
│   └── utils.py
│
├── shared/
│   └── langs.py
│
├── tools/
│   └── classify.py
│
├── fetch.py
├── classify.py
├── to_csv.py
├── utils.py
├── requirements.txt
├── .env
└── .gitignore
```

---

## Installation

### Requirements

- Python 3.11+
- Chromium dependencies for Playwright

Install dependencies:

```bash
pip install -r requirements.txt
```

Install Playwright browser binaries:

```bash
playwright install chromium
```

---

## Configuration

Create a `.env` file in the project root:

```env
ENTREZ_EMAIL=your@email.com
ENTREZ_API_KEY=your_ncbi_api_key
SCIELO_COOKIE=

QUERIES=renal physiology,cardiovascular physiology
```

### Environment Variables

| Variable | Description |
|---|---|
| `ENTREZ_EMAIL` | Email required by NCBI Entrez |
| `ENTREZ_API_KEY` | Optional API key for higher PubMed rate limits |
| `SCIELO_COOKIE` | Automatically refreshed when expired |
| `QUERIES` | Comma-separated query list |

---

## Usage

### Run Data Collection

```bash
python fetch.py
```

This command:

- Executes all configured queries
- Fetches data from PubMed, ArXiv, and SciELO
- Runs fetchers in parallel
- Stores raw results in `data/dataset_raw.jsonl`
- Saves checkpoints for resumable execution

---

### Run Classification and Deduplication

```bash
python classify.py
```

This step:

- Removes duplicate article IDs
- Normalizes language labels
- Separates datasets by query/topic
- Generates statistics reports
- Outputs classified datasets into `data/classified/`

---

### Export to CSV

```bash
python to_csv.py
```

Converts generated JSONL datasets into CSV format.

---

## Dataset Format

Each line in the dataset is stored as a JSON object:

```json
{
  "source": "scielo",
  "query": "renal physiology",
  "id": "S0080-62342026000100413",
  "url": "https://example.org/article",
  "title": "Impact of invasive mechanical ventilation...",
  "abstracts": {
    "english": "ABSTRACT...",
    "portuguese": "RESUMO...",
    "spanish": "RESUMEN..."
  },
  "languages": [
    "english",
    "portuguese",
    "spanish"
  ],
  "multilingual": true
}
```

---

## Generated Report Example

```json
{
  "total_raw": 79840,
  "total_after_dedup": 79123,
  "duplicates_removed": 717,
  "multilingual_entries": 636,
  "by_query": {
    "renal physiology": 9671
  },
  "by_source": {
    "pubmed": 78248,
    "scielo": 875
  },
  "by_language": {
    "english": 77549,
    "spanish": 478,
    "portuguese": 305
  }
}
```

---

## Language Normalization

Pesquisa normalizes language codes into canonical language names.

Examples:

| Raw Code | Normalized |
|---|---|
| `en` | `english` |
| `eng` | `english` |
| `pt` | `portuguese` |
| `es` | `spanish` |

The project currently supports 40+ ISO-639 language mappings.

---

## SciELO Anti-Block System

SciELO uses CDN-level anti-bot protections. Pesquisa includes a dedicated handling layer for stable collection.

### Protection Handling Features

- Real Chromium fingerprinting through Playwright
- Async article retrieval through aiohttp
- Automatic cookie refresh system
- Retry and block detection logic
- Adaptive delay and backoff strategies
- Query abort safeguards after repeated failures

This hybrid approach allows faster scraping while minimizing block frequency.

---

## Checkpointing

Progress is automatically persisted after query execution.

If the pipeline stops unexpectedly:

- Previously processed IDs are skipped
- Completed queries are preserved
- Collection resumes safely without duplication

---

## Performance Notes

### PubMed

- Up to 20,000 results per query
- Batched in groups of 200
- Higher rate limits available with NCBI API keys

### ArXiv

- Up to 20,000 results per query
- Batched in groups of 100

### SciELO

- Pagination continues until no additional results are found
- Adaptive delays reduce block probability

---

## Use Cases

Pesquisa can be used for:

- Scientific NLP datasets
- Multilingual language modeling
- Research trend analysis
- Biomedical abstract mining
- Academic search indexing
- Topic clustering pipelines
- RAG dataset preparation
- Translation and multilingual corpora generation

---

## Example Workflow

```bash
# 1. Configure queries
nano .env

# 2. Fetch datasets
python fetch.py

# 3. Deduplicate and classify
python classify.py

# 4. Export CSV if needed
python to_csv.py
```

---

## Future Improvements

Potential roadmap ideas:

- Semantic deduplication using embeddings
- PDF full-text extraction
- Additional scientific sources
- Distributed fetching workers
- PostgreSQL dataset backend
- FAISS/vector database integration
- HuggingFace dataset export
- Advanced metadata enrichment
- Automatic topic modeling

---

## Contributing

Contributions are welcome.

Suggested areas:

- New source integrations
- Improved anti-block systems
- Performance optimizations
- Metadata extraction improvements
- Additional export formats
- Better language detection

---

## License

This repository currently does not define a license.

Consider adding a license file before public distribution or external contributions.

---

## Acknowledgements

- NCBI Entrez API
- ArXiv API
- SciELO
- Playwright
- aiohttp

