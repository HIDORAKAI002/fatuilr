# oauth_server.py
import os
import requests
import asyncio
from flask import Flask, request, redirect
from dotenv import load_dotenv
from storage import store_discord_tokens
from discord_bot import push_role_metadata

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("COOKIE_SECRET")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

@app.route("/")
def index():
    return "OAuth server is running. Use /login to link your role."

@app.route("/login")
def login():
    scope = "identify role_connections.write"
    return redirect(
        f"https://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={scope}"
    )

@app.route("/discord-oauth-callback")
def callback():
    code = request.args.get("code")
    if not code:
        return "Error: No code provided from Discord.", 400

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": REDIRECT_URI,
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    token_response = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    tokens = token_response.json()

    if "access_token" not in tokens:
        return "Error fetching access token.", 500

    user_response = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    user = user_response.json()
    user_id = int(user["id"])

    store_discord_tokens(user_id, tokens)
    
    # Capture the return value from push_role_metadata
    was_role_granted = asyncio.run(push_role_metadata(user_id, tokens))

    if was_role_granted:
        # The user had a role and the badge was successfully granted
        return f"✅ Success! Your roles have been linked, {user['username']}. You can now close this tab."
    else:
        # The user had no valid roles
        return f"❌ Verification Failed.Sybau lil bro dont even try"