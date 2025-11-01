# oauth_server.py
import os
import requests
import asyncio
from flask import Flask, request, redirect
from dotenv import load_dotenv
from storage import store_discord_tokens # This is a simple storage
# Import the bot object and the push_role_metadata function
from discord_bot import push_role_metadata, bot

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("COOKIE_SECRET")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

# --- HTML TEMPLATES ---
# (I've removed the HTML to save space, but you can paste your plain-text or image HTML here)
SUCCESS_HTML = "✅ Success! Your roles have been linked, {username}. You can now close this tab."
FAILURE_HTML = "❌ Sybau lil bro you don't even ahve the role."

# --- END OF HTML TEMPLATES ---


@app.route("/")
def index():
    return "OAuth server is running. Use /login to link your role."

@app.route("/login")
def login():
    # This scope does NOT include 'offline'
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

    access_token = tokens['access_token']

    user_response = requests.get("https://discord.com/api/users/@me", headers={"Authorization": f"Bearer {access_token}"})
    user = user_response.json()
    user_id = int(user["id"])

    # This just saves the token, it's not used again by this simple bot
    store_discord_tokens(user_id, tokens) 
    
    # Pass the initial access_token and user info to the bot for the first push
    was_role_granted = asyncio.run(push_role_metadata(user_id, access_token, user))

    if was_role_granted:
        return SUCCESS_HTML.format(username=user['username'])
    else:
        return FAILURE_HTML
