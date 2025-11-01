# oauth_server.py
import os
import requests
import asyncio
from flask import Flask, request, redirect
from dotenv import load_dotenv
from storage import store_discord_tokens
# UPDATED: Import the bot object as well
from discord_bot import push_role_metadata, bot

load_dotenv()

app = Flask(__name__)
app.secret_key = os.getenv("COOKIE_SECRET")

CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
REDIRECT_URI = os.getenv("DISCORD_REDIRECT_URI")

# --- HTML TEMPLATES ---

SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Success!</title>
    <style>
        body { background-color: #2c2f33; color: #ffffff; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; display: grid; place-items: center; min-height: 90vh; }
        .container { background-color: #36393f; padding: 40px; border-radius: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.3); text-align: center; }
        h1 { color: #4CAF50; }
    </style>
</head>
<body>
    <div class="container">
        <h1>✅ Success!</h1>
        <p>Your roles have been linked, {username}.</p>
        <p>You can now close this tab.</p>
    </div>
</body>
</html>
"""

FAILURE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Verification Failed</title>
    <style>
        body, html {
            margin: 0;
            padding: 0;
            height: 100%;
            width: 100%;
            background-color: #1e1f22;
            /* PASTE YOUR IMAGE URL HERE */
            background-image: linear-gradient(rgba(0, 0, 0, 0.5), rgba(0, 0, 0, 0.5)), url('https://raw.githubusercontent.com/HIDORAKAI002/fatuilr/main/assets/f-u-middle-finger.png');
            background-position: center;
            background-repeat: no-repeat;
            background-size: cover;
            
            /* Center the text container */
            display: grid;
            place-items: center;
            font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif;
            color: #ffffff;
        }
        .container { 
            background-color: rgba(44, 47, 51, 0.8); /* Semi-transparent container */
            padding: 40px; 
            border-radius: 10px; 
            box-shadow: 0 4px 14px rgba(0,0,0,0.3); 
            text-align: center; 
        }
        h1 { color: #F44336; }
    </style>
</head>
<body>
    <div class="container">
        <h1>❌ Verification Failed</h1>
        <p>You do not have any of the required roles in the server.</p>
        <p>You can close this tab.</p>
    </div>
</body>
</html>
"""

# --- END OF HTML TEMPLATES ---


@app.route("/")
def index():
    return "OAuth server is running. Use /login to link your role."

@app.route("/login")
def login():
    scope = "identify role_connections.write"
    return redirect(
        f"httpsS://discord.com/api/oauth2/authorize?client_id={CLIENT_ID}&redirect_uri={REDIRECT_URI}&response_type=code&scope={scope}"
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
    
    token_response = requests.post("httpsS://discord.com/api/oauth2/token", data=data, headers=headers)
    tokens = token_response.json()

    if "access_token" not in tokens:
        return "Error fetching access token.", 500

    user_response = requests.get("httpsS://discord.com/api/users/@me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    user = user_response.json()
    user_id = int(user["id"])

    store_discord_tokens(user_id, tokens)
    
    # UPDATED: Pass the 'user' object to the bot for logging
    was_role_granted = asyncio.run(push_role_metadata(user_id, tokens, user))

    if was_role_granted:
        return SUCCESS_HTML.format(username=user['username'])
    else:
        return FAILURE_HTML
