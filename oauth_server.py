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

# --- HTML Templates ---
SUCCESS_HTML = "✅ Success! Your roles have been linked, {username}. You can now close this tab."
FAILURE_HTML = "❌ Verification Failed. You do not have any of the required roles in the server. You can close this tab."
# --- End of HTML Templates ---


@app.route("/")
def index():
    return "OAuth server is running. Use /login to link your role."


@app.route("/login")
def login():
    # ✅ Correct Discord OAuth2 Scopes for Linked Roles
    scope = "identify guilds.members.read role_connections.write"

    # ✅ Properly encoded redirect URI
    return redirect(
        f"https://discord.com/api/oauth2/authorize"
        f"?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&prompt=consent"
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

    # Exchange the authorization code for access and refresh tokens
    token_response = requests.post("https://discord.com/api/oauth2/token", data=data, headers=headers)
    tokens = token_response.json()

    if "access_token" not in tokens:
        return f"Error fetching access token: {tokens}", 500

    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    expires_in = tokens.get("expires_in")

    # Fetch the user's info
    user_response = requests.get(
        "https://discord.com/api/users/@me",
        headers={"Authorization": f"Bearer {access_token}"}
    )
    user = user_response.json()

    if "id" not in user:
        return f"Error fetching user data: {user}", 500

    user_id = int(user["id"])

    # Store tokens for later use
    store_discord_tokens(user_id, access_token, refresh_token, expires_in)

    # Push Linked Role metadata immediately
    was_role_granted = asyncio.run(push_role_metadata(user_id, access_token, user))

    if was_role_granted:
        return SUCCESS_HTML.format(username=user["username"])
    else:
        return FAILURE_HTML


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 8080)))
