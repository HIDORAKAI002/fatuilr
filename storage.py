# storage.py
import json
import os

STORE_FILE = "tokens.json"

if os.path.exists(STORE_FILE):
    with open(STORE_FILE, "r") as f:
        store = json.load(f)
else:
    store = {}

def _save_store():
    with open(STORE_FILE, "w") as f:
        json.dump(store, f, indent=4)

def store_discord_tokens(user_id: int, tokens: dict):
    store[f"discord-{user_id}"] = tokens
    _save_store()

def get_discord_tokens(user_id: int):
    return store.get(f"discord-{user_id}")