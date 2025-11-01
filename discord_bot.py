# discord_bot.py
import os
import discord
import aiohttp
import time
from dotenv import load_dotenv
# Import our new storage functions
from storage import get_discord_tokens, update_access_token

load_dotenv()

# --- Load Config from .env ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) 
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
CLIENT_SECRET = os.getenv("DISCORD_CLIENT_SECRET") # We need the secret to refresh tokens
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# --- Bot Setup ---
intents = discord.Intents.default()
intents.members = True # REQUIRED
bot = discord.Client(intents=intents)

# ------------------- Roles Mapping -------------------
ROLE_MAPPING = [
    {"key": "has_founder",   "role_id": 1400496639680057407, "name": "Founder"},
    {"key": "has_c_suit",    "role_id": 1432535953712615486, "name": "The C Suit"},
    {"key": "has_nexus",     "role_id": 1432769935590818005, "name": "The Nexus"},
    {"key": "has_as_suites", "role_id": 1433905673275703349, "name": "Assisting Suites"},
    {"key": "has_as_nexus",  "role_id": 1434247577251090453, "name": "Assisting Nexus"},
]

# ------------------- Metadata Schema -------------------
ROLE_METADATA = [
    {
        "key": role["key"],
        "name": role["name"],
        "description": f"Has the {role['name']} role in the server",
        "type": 7  # 7 = boolean_equal
    }
    for role in ROLE_MAPPING
]

# --- NEW: Bot Event for Role Changes ---
@bot.event
async def on_member_update(before: discord.Member, after: discord.Member):
    """
    This event triggers automatically when a user's roles change.
    """
    # If the roles haven't changed, do nothing
    if before.roles == after.roles:
        return
    
    print(f"Role change detected for user {after.name}. Triggering update.")
    # Call our new function to handle the update
    await update_roles_for_member(after)


# --- NEW: Function to Refresh Tokens ---
async def get_new_access_token(user_id: int) -> str | None:
    """
    Uses a refresh token to get a new access token from Discord.
    """
    tokens = get_discord_tokens(user_id)
    if not tokens:
        print(f"No tokens found for user {user_id} during refresh.")
        return None

    data = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": tokens['refresh_token'],
    }
    headers = {"Content-Type": "application/x-www-form-urlencoded"}

    async with aiohttp.ClientSession() as session:
        async with session.post("https://discord.com/api/oauth2/token", data=data, headers=headers) as resp:
            if resp.status != 200:
                print(f"Error refreshing token for user {user_id}: {await resp.text()}")
                # If refresh fails (e.g., user revoked app), we can't do anything
                return None
            
            new_tokens = await resp.json()
            # Save the new tokens
            update_access_token(
                user_id,
                new_tokens['access_token'],
                new_tokens['refresh_token'],
                new_tokens['expires_in']
            )
            print(f"Successfully refreshed token for user {user_id}")
            return new_tokens['access_token']

# --- MODIFIED: Core Metadata Push Function ---
async def push_metadata(user_id: int, access_token: str, metadata: dict):
    """
    Pushes the metadata payload to Discord's API using a given access token.
    """
    url = f"https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"metadata": metadata}

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=payload) as resp:
            print(f"Metadata push for user {user_id} returned status: {resp.status}")
            if resp.status == 401:
                # 401 Unauthorized, token might be expired or invalid
                print(f"Got 401 for user {user_id}. Token may be invalid.")
                return "RETRY" # Special signal to retry with a new token
            
            if resp.status != 200:
                print(f"Error pushing metadata: {await resp.text()}")
                return "FAIL"
            
            return "SUCCESS"

# --- NEW: Main Function for Bot-side Updates ---
async def update_roles_for_member(member: discord.Member):
    """
    This is the main function called by the bot (e.g., on_member_update).
    It handles getting valid tokens and pushing the new role state.
    """
    user_id = member.id
    tokens = get_discord_tokens(user_id)
    
    if not tokens:
        # This user hasn't linked their role via the web, so we can't update them.
        return

    access_token = tokens['access_token']
    
    # Check if token is expired (with a 60-second buffer)
    if tokens['expires_at'] < (int(time.time()) + 60):
        print(f"Token expired for user {user_id}. Refreshing...")
        access_token = await get_new_access_token(user_id)
        if not access_token:
            print(f"Failed to refresh token for {user_id}. Aborting update.")
            return

    # Now we have a valid access_token (either old or new)
    # Get the member's current roles
    member_roles = [role.id for role in member.roles]
    metadata = {}
    found_role = False

    for role in ROLE_MAPPING:
        if role["role_id"] in member_roles:
            metadata[role["key"]] = 1  # True
            found_role = True
        else:
            metadata[role["key"]] = 0  # False

    # Log before pushing
    user_full_name = f"{member.name}#{member.discriminator}"
    if not found_role:
        print(f"❌ User {user_full_name} has no mapped roles. Clearing any existing badge.")
        log_embed_color = discord.Color.red()
        log_embed_title = "Linked Role Cleared (Auto)"
        log_embed_desc = f"User **{user_full_name}** (`{user_id}`) no longer has a required role. Their badge has been removed."
    else:
        print(f"✅ Pushing metadata for user {user_full_name}: {metadata}")
        log_embed_color = discord.Color.blue()
        log_embed_title = "Linked Role Updated (Auto)"
        log_embed_desc = f"User **{user_full_name}** (`{user_id}`) roles changed. Their badge has been updated."
        
    # --- Try to push the metadata ---
    status = await push_metadata(user_id, access_token, metadata)
    
    if status == "RETRY":
        print(f"Token failed for {user_id} on first try. Refreshing and retrying...")
        access_token = await get_new_access_token(user_id)
        if access_token:
            # Retry the push with the brand new token
            status = await push_metadata(user_id, access_token, metadata)
        else:
            status = "FAIL"
            
    # Now log the final result
    if status == "FAIL":
        log_embed_title = "Linked Role Update FAILED"
        log_embed_desc = f"Failed to update roles for **{user_full_name}** (`{user_id}`). They may need to re-link manually."
        log_embed_color = discord.Color.dark_red()

    log_embed = discord.Embed(
        title=log_embed_title,
        description=log_embed_desc,
        color=log_embed_color
    )
    await log_to_discord(log_embed)

# --- OLD: Function for Web Server (First Push) ---
# This function is called by oauth_server.py only ONCE.
async def push_role_metadata(user_id: int, access_token: str, user_info: dict) -> bool:
    """
    Checks user roles and pushes metadata. Returns True if a badge was granted, False otherwise.
    This is ONLY called by the web server on initial link.
    """
    # We must wait for the bot to be ready to get the guild
    await bot.wait_until_ready()
    member = None
    guild = bot.get_guild(GUILD_ID)
    if guild:
        member = guild.get_member(user_id)

    if not member:
        # User is not in the server
        print(f"❌ User {user_id} is not in the guild. No role granted.")
        return False
        
    member_roles = [role.id for role in member.roles]
    metadata = {}
    found_role = False
    
    username = user_info.get('username', 'UnknownUser')
    user_discriminator = user_info.get('discriminator', '0000')
    user_full_name = f"{username}#{user_discriminator}"

    for role in ROLE_MAPPING:
        if role["role_id"] in member_roles:
            metadata[role["key"]] = 1
            found_role = True
        else:
            metadata[role["key"]] = 0

    if not found_role:
        print(f"❌ User {user_full_name} has no mapped roles. Clearing badge.")
        await push_metadata(user_id, access_token, {})
        
        log_embed = discord.Embed(
            title="Verification Failed (Manual)",
            description=f"User **{user_full_name}** (`{user_id}`) attempted to link, but had no required roles.",
            color=discord.Color.red()
        )
        await log_to_discord(log_embed)
        return False
    else:
        print(f"✅ Pushing metadata for user {user_full_name}: {metadata}")
        status = await push_metadata(user_id, access_token, metadata)
        
        log_embed = discord.Embed(
            title="Verification Success (Manual)",
            description=f"User **{user_full_name}** (`{user_id}`) successfully linked their roles.",
            color=discord.Color.green()
        )
        await log_to_discord(log_embed)
        return status == "SUCCESS"

# --- Logging Function ---
async def log_to_discord(message_embed):
    """Sends a log message (as an embed) to the specified channel."""
    try:
        await bot.wait_until_ready()
        channel = bot.get_channel(LOG_CHANNEL_ID)
        
        if channel:
            await channel.send(embed=message_embed)
        else:
            print(f"Error: Log channel {LOG_CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error logging to Discord: {e}")
