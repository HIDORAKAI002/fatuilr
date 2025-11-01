# discord_bot.py
import os
import discord
import aiohttp
from dotenv import load_dotenv

load_dotenv()

# --- Load Config from .env ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GUILD_ID = int(os.getenv("GUILD_ID")) 
CLIENT_ID = os.getenv("DISCORD_CLIENT_ID")
# NEW: Get the log channel ID
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID"))

# --- Bot Setup ---
intents = discord.Intents.default()
intents.members = True # REQUIRED to see member roles
bot = discord.Client(intents=intents)

# ------------------- Roles Mapping (Boolean Toggle System) -------------------
ROLE_MAPPING = [
    {"key": "has_founder",   "role_id": 1400496639680057407, "name": "Founder"},
    {"key": "has_c_suit",    "role_id": 1432535953712615486, "name": "The C Suit"},
    {"key": "has_nexus",     "role_id": 1432769935590818005, "name": "The Nexus"},
    {"key": "has_as_suites", "role_id": 1433905673275703349, "name": "Assisting Suites"},
    {"key": "has_as_nexus",  "role_id": 1434247577251090453, "name": "Assisting Nexus"},
]

# This creates the schema for our 5 boolean metadata fields
ROLE_METADATA = [
    {
        "key": role["key"],
        "name": role["name"],
        "description": f"Has the {role['name']} role in the server",
        "type": 7  # 7 = boolean_equal
    }
    for role in ROLE_MAPPING
]

# --- NEW: Logging Function ---
async def log_to_discord(message_embed):
    """Sends a log message (as an embed) to the specified channel."""
    try:
        # Wait until the bot is ready
        await bot.wait_until_ready()
        channel = bot.get_channel(LOG_CHANNEL_ID)
        
        if channel:
            await channel.send(embed=message_embed)
        else:
            print(f"Error: Log channel {LOG_CHANNEL_ID} not found.")
    except Exception as e:
        print(f"Error logging to Discord: {e}")

# --- Core Functions ---
async def get_member_roles(user_id: int):
    guild = bot.get_guild(GUILD_ID)
    if not guild:
        print(f"❌ Guild with ID {GUILD_ID} not found.")
        return []
    member = guild.get_member(user_id)
    if not member:
        return []
    return [role.id for role in member.roles]

async def push_metadata(user_id: int, tokens: dict, metadata: dict):
    url = f"https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection"
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    payload = {"metadata": metadata}

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=payload) as resp:
            print(f"Metadata push for user {user_id} returned status: {resp.status}")
            if resp.status != 200:
                print(f"Error pushing metadata: {await resp.text()}")
                return False
            return True

async def push_role_metadata(user_id: int, tokens: dict, user_info: dict):
    """Checks user roles, pushes metadata, and logs the result. Returns True if a badge was granted."""
    member_roles = await get_member_roles(user_id)
    metadata = {}
    found_role = False
    
    username = user_info.get('username', 'UnknownUser')
    user_discriminator = user_info.get('discriminator', '0000')
    user_full_name = f"{username}#{user_discriminator}"

    # For each role we track, set its key to 1 if the user has the role, otherwise 0
    for role in ROLE_MAPPING:
        if role["role_id"] in member_roles:
            metadata[role["key"]] = 1
            found_role = True
        else:
            metadata[role["key"]] = 0

    if not found_role:
        # User has none of the required roles.
        print(f"❌ User {user_full_name} has no mapped roles. Clearing any existing badge.")
        await push_metadata(user_id, tokens, {})
        
        # Log the failure
        log_embed = discord.Embed(
            title="Verification Failed",
            description=f"User **{user_full_name}** (`{user_id}`) attempted to link their roles but had no required roles.",
            color=discord.Color.red()
        )
        await log_to_discord(log_embed)
        
        return False # No role found
    else:
        # User has at least one role. Grant the badge(s).
        print(f"✅ Pushing metadata for user {user_full_name}: {metadata}")
        success = await push_metadata(user_id, tokens, metadata)
        
        # Log the success
        log_embed = discord.Embed(
            title="Verification Success",
            description=f"User **{user_full_name}** (`{user_id}`) successfully linked their roles.",
            color=discord.Color.green()
        )
        await log_to_discord(log_embed)
        
        return success
