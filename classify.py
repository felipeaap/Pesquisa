# tools/classify.py
import json
from pathlib import Path
from collections import defaultdict
from utils.files import load_jsonl, slug, RAW_FILE, CLASSIFIED_DIR, REPORT_FILE
from utils.classify import normalize_date, classify_languages, dedup

def build_report(original, by_query, all_dupes) -> dict:
    lang_counts   = defaultdict(int)
    source_counts = defaultdict(int)
    query_counts  = {}
    multilingual  = 0

    for query, entries in by_query.items():
        query_counts[query] = len(entries)
        for entry in entries:
            source_counts[entry.get("source", "unknown")] += 1
            for lang in entry.get("languages", []):
                lang_counts[lang] += 1
            if entry.get("multilingual"):
                multilingual += 1

    return {
        "total_raw":            len(original),
        "total_after_dedup":    sum(len(v) for v in by_query.values()),
        "duplicates_removed":   len(all_dupes),
        "multilingual_entries": multilingual,
        "by_query":             dict(sorted(query_counts.items())),
        "by_source":            dict(source_counts),
        "by_language":          dict(sorted(lang_counts.items(), key=lambda x: -x[1])),
        "duplicate_ids":        [d["id"] for d in all_dupes],
    }


def classify():
    print(f"[Classify] Loading {RAW_FILE}...")
    entries = load_jsonl(RAW_FILE)
    print(f"[Classify] Loaded {len(entries)} entries")

    deduped, dupes = dedup(entries)
    print(f"[Classify] {len(dupes)} duplicates removed → {len(deduped)} unique entries")

    classified = [classify_languages(e) for e in deduped]

    # group by query — each query becomes its own output file
    by_query = defaultdict(list)
    for entry in classified:
        query = entry.get("query", "unknown")
        by_query[query].append(entry)

    output_dir = Path(CLASSIFIED_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    for query, items in by_query.items():
        out_path = output_dir / f"{slug(query)}.jsonl"
        with open(out_path, "w", encoding="utf-8") as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")
        print(f"[Classify] {query!r:<40} → {len(items):>5} entries → {out_path.name}")

    report = build_report(entries, by_query, dupes)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n[Classify] Done → {CLASSIFIED_DIR}/")
    print(f"[Classify] Report → {REPORT_FILE}")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    classify() 