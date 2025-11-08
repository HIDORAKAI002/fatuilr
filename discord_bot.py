# discord_bot.py
import os
import discord
import aiohttp
import time
import threading
from flask import Flask
from dotenv import load_dotenv
from storage import get_discord_tokens, update_access_token

load_dotenv()

# --- Load Config from .env ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID"))
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# --- Bot Setup ---
intents = discord.Intents.default()
intents.members = True
bot = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(bot)

# ------------------- Roles Mapping -------------------
ROLE_MAPPING = [
    {"key": "has_founder", "role_id": 1400496639680057407, "name": "Founder"},
    {"key": "has_c_suit", "role_id": 1432535953712615486, "name": "The C Suit"},
    {"key": "has_nexus", "role_id": 1432769935590818005, "name": "The Nexus"},
    {"key": "has_as_suites", "role_id": 1433905673275703349, "name": "Assisting Suites"},
    {"key": "has_as_nexus", "role_id": 1434247577251090453, "name": "Assisting Nexus"},
]

# ------------------- Metadata Schema -------------------
ROLE_METADATA = [
    {
        "key": role["key"],
        "name": role["name"],
        "description": f"Has the {role['name']} role in the server",
        "type": 7
    }
    for role in ROLE_MAPPING
]

# --- Role Change Event ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    if before.roles == after.roles:
        return
    print(f"Role change detected for user {after.name}.")
    await update_roles_for_member(after)

# --- Refresh Access Tokens ---
async def get_new_access_token(user_id: int) -> str | None:
    tokens = get_discord_tokens(user_id)
    if not tokens:
        print(f"No tokens found for user {user_id}.")
        return None

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": tokens["refresh_token"],
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://discord.com/api/oauth2/token", data=data, headers=headers) as resp:
            if resp.status != 200:
                print(f"Error refreshing token for {user_id}: {await resp.text()}")
                return None

            new_tokens = await resp.json()
            update_access_token(
                user_id,
                new_tokens["access_token"],
                new_tokens["refresh_token"],
                new_tokens["expires_in"],
            )
            print(f"Successfully refreshed token for {user_id}")
            return new_tokens["access_token"]

# --- Push Role Metadata ---
async def push_metadata(user_id: int, access_token: str, metadata: dict):
    url = f"https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"metadata": metadata}

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=payload) as resp:
            print(f"Metadata push for user {user_id} returned {resp.status}")
            if resp.status == 401:
                return "RETRY"
            if resp.status != 200:
                print(f"Error pushing metadata: {await resp.text()}")
                return "FAIL"
            return "SUCCESS"

# --- Update Roles Automatically ---
async def update_roles_for_member(member: discord.Member):
    user_id = member.id
    tokens = get_discord_tokens(user_id)
    if not tokens:
        return

    access_token = tokens["access_token"]
    if tokens["expires_at"] < (int(time.time()) + 60):
        print(f"Token expired for {user_id}. Refreshing...")
        access_token = await get_new_access_token(user_id)
        if not access_token:
            print(f"Failed to refresh token for {user_id}.")
            return

    member_roles = [r.id for r in member.roles]
    metadata = {r["key"]: int(r["role_id"] in member_roles) for r in ROLE_MAPPING}
    found_role = any(metadata.values())

    user_full_name = f"{member.name}#{member.discriminator}"
    if not found_role:
        print(f"❌ {user_full_name} has no mapped roles.")
        color = discord.Color.red()
        title = "Linked Role Cleared (Auto)"
        desc = f"{user_full_name} (`{user_id}`) lost all linked roles."
    else:
        print(f"✅ Updating metadata for {user_full_name}: {metadata}")
        color = discord.Color.blue()
        title = "Linked Role Updated (Auto)"
        desc = f"{user_full_name} (`{user_id}`) roles updated."

    status = await push_metadata(user_id, access_token, metadata)
    if status == "RETRY":
        access_token = await get_new_access_token(user_id)
        if access_token:
            status = await push_metadata(user_id, access_token, metadata)
        else:
            status = "FAIL"

    if status == "FAIL":
        title = "Linked Role Update FAILED"
        desc = f"Failed to update roles for {user_full_name}."
        color = discord.Color.dark_red()

    embed = discord.Embed(title=title, description=desc, color=color)
    await log_to_discord(embed)

# --- Initial Metadata Push from OAuth ---
async def push_role_metadata(user_id: int, access_token: str, user_info: dict) -> bool:
    await bot.wait_until_ready()
    guild = bot.get_guild(GUILD_ID)
    member = guild.get_member(user_id) if guild else None

    if not member:
        print(f"❌ {user_id} not found in guild.")
        return False

    member_roles = [r.id for r in member.roles]
    metadata = {r["key"]: int(r["role_id"] in member_roles) for r in ROLE_MAPPING}
    found_role = any(metadata.values())

    username = user_info.get("username", "UnknownUser")
    discrim = user_info.get("discriminator", "0000")
    full_name = f"{username}#{discrim}"

    if not found_role:
        print(f"❌ {full_name} has no mapped roles.")
        await push_metadata(user_id, access_token, {})
        embed = discord.Embed(
            title="Verification Failed (Manual)",
            description=f"{full_name} (`{user_id}`) had no eligible roles.",
            color=discord.Color.red(),
        )
        await log_to_discord(embed)
        return False
    else:
        print(f"✅ Linking roles for {full_name}: {metadata}")
        status = await push_metadata(user_id, access_token, metadata)
        embed = discord.Embed(
            title="Verification Success (Manual)",
            description=f"{full_name} (`{user_id}`) successfully linked.",
            color=discord.Color.green(),
        )
        await log_to_discord(embed)
        return status == "SUCCESS"

# --- Remove Linked Role Connection ---
async def remove_role_metadata(user_id: int, access_token: str):
    import requests
    url = f"https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection"
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"platform_name": None, "platform_username": None, "metadata": {}}
    response = requests.put(url, headers=headers, json=data)
    if response.status_code == 200:
        print(f"[LinkedRoles] Successfully unlinked {user_id}")
        return True
    else:
        print(f"[LinkedRoles] Failed to unlink {user_id}: {response.text}")
        return False

# --- Log Function ---
async def log_to_discord(embed):
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(LOG_CHANNEL_ID)
        if channel:
            await channel.send(embed=embed)
        else:
            print(f"Error: Log channel {LOG_CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error logging: {e}")

# --- /unlink Command ---
@tree.command(name="unlink", description="Force-remove a user's Linked Role connection.")
@discord.app_commands.checks.has_permissions(manage_roles=True)
async def unlink(interaction: discord.Interaction, user: discord.User):
    await interaction.response.defer(ephemeral=True)
    tokens = get_discord_tokens(user.id)
    if not tokens or "access_token" not in tokens:
        await interaction.followup.send(f"⚠️ No linked data found for {user.mention}.", ephemeral=True)
        return

    access_token = tokens["access_token"]
    success = await remove_role_metadata(user.id, access_token)

    if success:
        await interaction.followup.send(f"✅ Successfully unlinked **{user.name}** from Linked Roles.", ephemeral=True)
    else:
        await interaction.followup.send(f"❌ Failed to unlink **{user.name}**. Please try again or reauthorize them.", ephemeral=True)

# --- Bot Ready Event ---
@bot.event
async def on_ready():
    await tree.sync()
    print(f"✅ Logged in as {bot.user} — slash commands synced.")

# --- Keep-alive Web Server for Render ---
app = Flask(__name__)

@app.route('/')
def home():
    return "Linked Role bot is online and running."

def run_web():
    port = int(os.getenv("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web).start()

# --- Run the Bot ---
bot.run(TOKEN)
