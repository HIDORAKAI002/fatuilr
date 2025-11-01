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

async def push_metadata(user_id: int, access_token: str, metadata: dict):
    """Pushes the metadata payload to Discord's API."""
    url = f"https://discord.com/api/v10/users/@me/applications/{CLIENT_ID}/role-connection"
    headers = {"Authorization": f"Bearer {access_token}"}
    payload = {"metadata": metadata}

    async with aiohttp.ClientSession() as session:
        async with session.put(url, headers=headers, json=payload) as resp:
            print(f"Metadata push for user {user_id} returned status: {resp.status}")
            if resp.status != 200:
                print(f"Error pushing metadata: {await resp.text()}")
                return False
            return True

# --- This function is called by the web server on login ---
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
        return status
