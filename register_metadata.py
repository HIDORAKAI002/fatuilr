# register_metadata.py
import os
import requests
from dotenv import load_dotenv
from discord_bot import CLIENT_ID, ROLE_METADATA

load_dotenv()
BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")

url = f"https://discord.com/api/v10/applications/{CLIENT_ID}/role-connections/metadata"

headers = {"Authorization": f"Bot {BOT_TOKEN}"}
json_payload = ROLE_METADATA

print("▶️  Attempting to register metadata with Discord...")
print(f"PAYLOAD: {json_payload}")

response = requests.put(url, headers=headers, json=json_payload)

print(f"\n✅ RESPONSE\n-----------------")
print(f"Status Code: {response.status_code}")
try:
    print(response.json())
except requests.exceptions.JSONDecodeError:
    print(response.text)
