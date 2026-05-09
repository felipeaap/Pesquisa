# Pesquisa — Coletor de Resumos de Fisiologia

Pipeline de dados para coleta, deduplicação e classificação de resumos científicos do **PubMed** e do **SciELO** em múltiplos idiomas.

---

## Visão Geral

O pipeline executa consultas em paralelo nas duas fontes, extrai resumos multilíngues, deduplica por ID do artigo e normaliza os rótulos de idioma em um dataset JSONL limpo.

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

## Estrutura do Projeto

```
.
├── data/
│   ├── output.jsonl          # resumos coletados brutos
│   ├── output_clean.jsonl    # deduplicados e classificados
│   └── report.json           # estatísticas da execução
├── pubmed/
│   ├── pubmed_fetcher.py     # coletor em lote via Entrez
│   └── utils.py              # extração de resumos, normalização de idioma
├── scielo/
│   ├── scielo_fetcher.py     # scraper Playwright + aiohttp
│   ├── block_guard.py        # lógica de retry, detecção de bloqueio, headers
│   ├── cookie.py             # renovação de cookie via Playwright
│   └── utils.py              # divisão de resumos, extração de PID
├── shared/
│   └── langs.py              # mapeamentos unificados de códigos e nomes de idioma
├── tools/
│   └── classify.py           # deduplicação + classificação de idioma
├── utils/
│   └── logger.py             # logger com controle de verbosidade
├── pub_getter.py             # ponto de entrada — executa os dois coletores em paralelo
├── queries.py                # carrega QUERIES do .env
├── utils.py                  # checkpoint, salvamento JSONL, hashing
├── .env                      # segredos e configurações (nunca versionado)
└── .gitignore
```

---

## Instalação

**Requisitos**: Python 3.11+

```bash
pip install aiohttp aiofiles beautifulsoup4 biopython playwright python-dotenv tqdm lxml Brotli
playwright install chromium
```

**Configure o `.env`:**

```env
ENTREZ_EMAIL=seu@email.com
ENTREZ_API_KEY=sua_chave_ncbi        # opcional — aumenta o limite de 3 para 10 req/s
SCIELO_COOKIE=                       # preenchido automaticamente na primeira execução
QUERIES=fisiologia renal,fisiologia cardiovascular,fisiologia respiratória
VERBOSE=0                            # defina como 1 para log detalhado por página
```

---

## Uso

**Executar o pipeline completo:**

```bash
python pub_getter.py
```

Coleta todas as consultas das duas fontes em paralelo, salva os resultados em `data/output.jsonl` e registra o progresso em checkpoint para retomar execuções interrompidas.

**Classificar e deduplicar:**

```bash
python -m tools.classify
```

Lê `data/output.jsonl`, remove IDs duplicados, normaliza os rótulos de idioma e gera `data/output_clean.jsonl` e `data/report.json`.

---

## Formato de Saída

Cada linha do JSONL de saída representa um artigo:

```json
{
  "source": "scielo",
  "query": "fisiologia renal",
  "id": "S0080-62342026000100413",
  "url": "http://...",
  "title": "Impacto da ventilação mecânica invasiva...",
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

## Formato do Relatório

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

## Suporte a Idiomas

Os resumos são normalizados para nomes completos de idioma (ex.: `"en"` → `"english"`, `"eng"` → `"english"`). São suportados códigos ISO 639-1 e ISO 639-2 de mais de 40 idiomas das famílias germânica, românica, eslava, semítica, do leste asiático e do sul/sudeste asiático.

---

## Tratamento de Bloqueios (SciELO)

O SciELO utiliza proteção anti-bot via Bunny CDN. O scraper lida com isso através de:

- **Playwright** para toda a paginação de busca (fingerprint TLS real do Chromium)
- **aiohttp** para busca de artigos individuais (mais rápido, CDN menos agressivo em URLs diretas)
- **Renovação automática de cookie** via Playwright ao detectar bloqueio
- **Limite de 3 tentativas** por página antes de abandonar a consulta
- **Delay adaptativo** que recua quando os resultados parecem escassos

Se o cookie expirar entre execuções, ele é renovado automaticamente na próxima execução.

---

## Checkpoint

O progresso é salvo após cada consulta. Ao reexecutar o pipeline, IDs já coletados são ignorados, permitindo retomar execuções interrompidas sem duplicar dados.

---

## Observações

- O PubMed coleta até 1000 resultados por consulta em lotes de 200 via API Entrez
- O SciELO pagina até que uma página retorne 0 resultados
- Uma chave de API gratuita do NCBI é recomendada — obtenha em [ncbi.nlm.nih.gov/account](https://www.ncbi.nlm.nih.gov/account/)