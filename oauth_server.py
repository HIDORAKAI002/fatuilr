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
        body { background-color: #2c2f33; color: #ffffff; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; display: grid; place-items: center; min-height: 90vh; }
        .container { background-color: #36393f; padding: 40px; border-radius: 10px; box-shadow: 0 4px 14px rgba(0,0,0,0.3); text-align: center; }
        h1 { color: #F44336; }
        video { max-width: 100%; border-radius: 8px; margin-bottom: 20px; }
    </style>
</head>
<body>
    <div class="container">
        <video src="https://cdn.discordapp.com/attachments/1412117348181213194/1434288938998042684/cat-laughing-video-meme-download.mp4?ex=6907c92a&is=690677aa&hm=3f63516a45a2fc3904b08b83f63ad3195768e5332575e593b549e4bbff9385b9&" width="350" autoplay loop>
            Your browser does not support the video tag.
        </video>
        
        <h1>❌ Verification Failed</h1>
        <p>You do not have the role (skill issue).</p>
        <p>Don't even try lil bro.</p>
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

    user_response = requests.get("https->discord.com/api/users/@me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    user = user_response.json()
    user_id = int(user["id"])

    store_discord_tokens(user_id, tokens)
    
    was_role_granted = asyncio.run(push_role_metadata(user_id, tokens))

    if was_role_granted:
        # The user had a role and the badge was successfully granted
        return SUCCESS_HTML.format(username=user['username'])
    else:
        # The user had no valid roles
        return FAILURE_HTML
