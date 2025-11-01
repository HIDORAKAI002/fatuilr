# storage.py
import json
import os
import time

STORE_FILE = "tokens.json"

# Load existing tokens from file or create an empty dictionary
if os.path.exists(STORE_FILE):
    with open(STORE_FILE, "r") as f:
        store = json.load(f)
else:
    store = {}

def _save_store():
    """Saves the current token store to the JSON file."""
    with open(STORE_FILE, "w") as f:
        json.dump(store, f, indent=4)

def store_discord_tokens(user_id: int, access_token: str, refresh_token: str, expires_in: int):
    """Stores all OAuth tokens for a user."""
    # Calculate the absolute time when the token expires
    expires_at = int(time.time()) + expires_in
    
    store[f"discord-{user_id}"] = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at
    }
    _save_store()

def get_discord_tokens(user_id: int):
    """Retrieves all tokens for a user."""
    return store.get(f"discord-{user_id}")

def update_access_token(user_id: int, new_access_token: str, new_refresh_token: str, new_expires_in: int):
    """Updates just the access token data after a refresh."""
    store_discord_tokens(user_id, new_access_token, new_refresh_token, new_expires_in)
