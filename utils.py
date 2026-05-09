import aiofiles
import json
import hashlib

OUTPUT_FILE = "datasets/dataset_raw.jsonl"
CHECKPOINT_FILE = "logs/checkpoint.json"
LOG_FILE = "logs/pipeline_log.jsonl"

async def log_event(event: dict):
    async with aiofiles.open(LOG_FILE, "a") as f:
        await f.write(json.dumps(event) + "\n")

def load_checkpoint():
    try:
        with open(CHECKPOINT_FILE, "r") as f:
            return json.load(f)
    except:
        return {"done_ids": []}


def save_checkpoint(state):
    with open(CHECKPOINT_FILE, "w") as f:
        json.dump(state, f)

async def save_jsonl_async(data):
    async with aiofiles.open(OUTPUT_FILE, "a", encoding="utf-8") as f:
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