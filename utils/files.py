import aiofiles
import json
import hashlib

CLASSIFIED_DIR = "data/classified"
REPORT_FILE = "data/report.json"
RAW_FILE = "data/dataset_raw.jsonl"
CHECKPOINT_FILE = "logs/checkpoint.json"
LOG_FILE = "logs/pipeline_log.jsonl"

def slug(query: str) -> str:
    """Convert query string to a safe filename."""
    return query.lower().strip().replace(" ", "_").replace("/", "_")

async def log_event(event: dict):
    async with aiofiles.open(LOG_FILE, "a") as f:
        await f.write(json.dumps(event) + "\n")

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    except:
        return {"done_ids": []}

def load_jsonl(path: str) -> list[dict]:
    entries = []
    with open(path, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError as e:
                print(f"[WARN] Line {i} is malformed, skipping: {e}")
    return entries

async def save_jsonl_async(data):
    async with aiofiles.open(RAW_FILE, "a", encoding="utf-8") as f:
        await f.write(json.dumps(data, ensure_ascii=False) + "\n")

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    except:
        return {"done_ids": []}


def save_checkpoint(state):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)

def hash_text(text):
    return hashlib.md5(text.encode()).hexdigest()