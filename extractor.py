import fitz
import re
from sentence_transformers import SentenceTransformer, util
from pathlib import Path
import json
from collections import defaultdict
import random
import numpy as np
from langdetect import detect, LangDetectException

def detect_language(text):
    try:
        return detect(text)
    except LangDetectException:
        return "unknown"
    
def balance(data):
    if not data:
        print("[WARN] Empty dataset, skipping balance")
        return data

    buckets = defaultdict(list)

    for d in data:
        buckets[d["label"]].append(d)

    if not buckets:
        print("[WARN] No labels found, skipping balance")
        return data

    min_size = min(len(v) for v in buckets.values())

    if min_size == 0:
        print("[WARN] Some classes are empty, skipping balance")
        return data

    final = []
    for k in buckets:
        final.extend(random.sample(buckets[k], min_size))

    return final

def save_json(dataset, path="dataset.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(dataset, f, ensure_ascii=False, indent=2)

QUERIES = [
    "renal physiology",
    "cardiovascular physiology",
    "respiratory physiology",
    "cellular physiology",
    "nervous physiology",
    "digestive physiology",
    "reproductive physiology",
    "endocrine physiology",
    "general physiology"
]

LABELS = [
    "renal",
    "cardiovascular",
    "respiratory",
    "digestive",
    "nervous",
    "endocrine",
    "reproductive",
    "cellular",
    "general"
]

LABEL_MAP = {
    # English
    "renal": "renal physiology",
    "kidney": "renal physiology",
    "cardio": "cardiovascular physiology",
    "heart": "cardiovascular physiology",
    "respiratory": "respiratory physiology",
    "lung": "respiratory physiology",
    "cell": "cellular physiology",
    "reproductive": "reproductive physiology",
    "endocrine": "endocrine physiology",
    "hormone": "endocrine physiology",

    # Portuguese
    "renal": "renal physiology",
    "rim": "renal physiology",
    "rins": "renal physiology",
    "cardiovascular": "cardiovascular physiology",
    "coração": "cardiovascular physiology",
    "cardiac": "cardiovascular physiology",
    "respirat": "respiratory physiology",   # covers respiratório, respiração
    "pulmon": "respiratory physiology",     # covers pulmonar, pulmão
    "celul": "cellular physiology",         # covers celular, células
    "reprodut": "reproductive physiology",  # covers reprodutivo, reprodução
    "endócrin": "endocrine physiology",     # covers endócrino, endócrina
    "hormôn": "endocrine physiology",       # covers hormônio, hormônios
    "digest": "digestive physiology",       # covers digestivo, digestão
    "nervos": "nervous physiology",
    "neural": "nervous physiology",
}

model = SentenceTransformer('all-MiniLM-L6-v2')
query_emb = model.encode(QUERIES, normalize_embeddings=True)

def clean_text(text):
    # fix hyphenated line breaks BEFORE collapsing newlines
    text = re.sub(r"-\n\s*", "", text)
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def extract_pdf(path):
    doc = fitz.open(path)
    pages = []

    for i, page in enumerate(doc):
        blocks = page.get_text("blocks")

        for b in blocks:
            x0, y0, x1, y1, text, *_ = b

            pages.append({
                "page": i,
                "text": clean_text(text),
                "bbox": (x0, y0, x1, y1)
            })

    return pages

def is_heading(text):
    text = text.strip()

    if len(text) < 5 or len(text) > 100:
        return False

    if text.isupper():
        return True

    if re.match(r"^\d+(\.\d+)*\s+", text):
        return True

    # unicode-safe title case: check each word starts with uppercase
    words = text.split()
    if len(words) <= 10 and all(w[0].isupper() for w in words if w.isalpha()):
        return True

    return False

def build_sections(blocks):
    sections = []
    current = {"title": "unknown", "content": []}

    for b in blocks:
        text = b["text"]

        if is_heading(text):
            if current["content"]:
                sections.append(current)

            current = {"title": text, "content": []}
        else:
            current["content"].append(text)

    # ✅ ALWAYS append fallback
    if current["content"]:
        sections.append(current)

    # 🔥 fallback if no headings detected
    if not sections:
        return [{
            "title": "full_text",
            "content": [b["text"] for b in blocks]
        }]

    return sections

def chunk_text(text, chunk_size=400, overlap=75):
    words = text.split()
    chunks = []

    i = 0
    while i < len(words):
        chunk = words[i:i+chunk_size]
        chunks.append(" ".join(chunk))
        i += chunk_size - overlap

    return chunks

def section_to_chunks(section):
    text = " ".join(section["content"])
    chunks = chunk_text(text)

    return [{
        "title": section["title"],
        "text": c
    } for c in chunks]

def title_label(title):
    t = title.lower()

    for k, v in LABEL_MAP.items():
        if k in t:
            return v, 0.95

    return None, 0.0

def semantic_label(text, top_k=2):
    emb = model.encode(text, normalize_embeddings=True)
    scores = util.cos_sim(emb, query_emb)[0].cpu().numpy()

    top_indices = np.argsort(scores)[::-1][:top_k]

    best_idx = top_indices[0]
    best_score = float(scores[best_idx])

    second_score = float(scores[top_indices[1]]) if len(top_indices) > 1 else 0.0
    margin = best_score - second_score

    return {
        "label": QUERIES[best_idx],
        "confidence": best_score,
        "margin": margin
    }

def label_chunks_batch(chunks):
    texts = [c["text"] for c in chunks]
    titles = [c["title"] for c in chunks]

    embs = model.encode(texts, normalize_embeddings=True, batch_size=32)
    scores = util.cos_sim(embs, query_emb)

    results = []

    for i in range(len(chunks)):
        row = scores[i].cpu().numpy()
        idx = row.argmax()

        best_score = float(row[idx])

        # margin
        sorted_idx = row.argsort()[::-1]
        second_score = float(row[sorted_idx[1]])
        margin = best_score - second_score

        # title override
        t_label, t_conf = title_label(titles[i])

        if t_conf > 0.9:
            label = t_label
            conf = t_conf
        elif best_score < 0.65 or margin < 0.1:
            label = "general physiology"
            conf = best_score
        else:
            label = QUERIES[idx]
            conf = best_score

        results.append((label, conf))

    return results

def build_dataset(pdf_paths):
    dataset = []

    for path in pdf_paths:
        print(f"[PDF] Processing: {path}")
        blocks = extract_pdf(path)
        print(f"  blocks extracted: {len(blocks)}")

        sections = build_sections(blocks)
        print(f"  sections built: {len(sections)}")

        for sec in sections:
            chunks = section_to_chunks(sec)
            if not chunks:
                continue

            labeled = label_chunks_batch(chunks)

            for ch, (label, conf) in zip(chunks, labeled):
                dataset.append({
                    "text": ch["text"],
                    "label": label,
                    "confidence": conf,
                    "section_title": ch["title"],
                    "source": path,
                    "lang": detect_language(ch["text"]),
                })

        print(f"  dataset so far: {len(dataset)}")

    return dataset

def pdf_paths(directory="extractor/pdfs", keyword=None):
    paths = list(Path(directory).rglob("*.pdf"))
    
    if keyword:
        paths = [p for p in paths if keyword.lower() in p.name.lower()]

    return [str(p) for p in paths]

def confidence_tier(c):
    if c > 0.75: return "high"
    if c > 0.6: return "medium"
    return "low"

paths = pdf_paths()
print(f"[PDF] Found {len(paths)} files")

dataset = build_dataset(paths)

print(f"[DEBUG] dataset size before filter: {len(dataset)}")

dataset = [d for d in dataset if d["confidence"] > 0.55]

dataset = [
    {**d, "confidence_tier": confidence_tier(d["confidence"])}
    for d in dataset
]

print(f"[DEBUG] dataset size after filter: {len(dataset)}")

dataset = balance(dataset)

save_json(dataset)