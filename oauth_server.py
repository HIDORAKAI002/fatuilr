# oauth_server.py
import os
import requests
import asyncio
from flask import Flask, request, redirect
from dotenv import load_dotenv
from storage import store_discord_tokens
# Import the bot object and the push_role_metadata function
from discord_bot import push_role_metadata, bot

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
    # We add 'offline' to the scope to get a refresh_token
    scope = "identify role_connections.write offline"
    return redirect(
        f"httpss://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={scope}&prompt=consent"
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
    
    token_response = requests.post("httpss://discord.com/api/oauth2/token", data=data, headers=headers)
    tokens = token_response.json()

    if "access_token" not in tokens or "refresh_token" not in tokens:
        return "Error fetching access token (maybe 'offline' scope is missing?).", 500

    # Get all the tokens we need
    access_token = tokens['access_token']
    refresh_token = tokens['refresh_token']
    expires_in = tokens['expires_in']

    user_response = requests.get("httpss://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access_token}"})
    user = user_response.json()
    user_id = int(user["id"])

    # Store ALL tokens for future offline use
    store_discord_tokens(user_id, access_token, refresh_token, expires_in)
    
    # Pass the initial access_token and user info to the bot for the first push
    was_role_granted = asyncio.run(push_role_metadata(user_id, access_token, user))

    if was_role_granted:
        return f"✅ Success! Your roles have been linked, {user['username']}. You can now close this tab."
    else:
        return f"❌ Verification Failed. You do not have any of the required roles in the server. You can close this tab."
