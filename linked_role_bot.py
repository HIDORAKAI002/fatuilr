# linked_role_bot.py
import os
import threading
from dotenv import load_dotenv
from discord_bot import bot
from oauth_server import app

load_dotenv()
PORT = int(os.environ.get("PORT", 3000))

if __name__ == "__main__":
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=PORT, use_reloader=False),
        daemon=True
    ).start()
    print(f"✅ OAuth server running on port {PORT}")

    print("✅ Starting Discord bot...")
    bot.run(os.getenv("DISCORD_BOT_TOKEN"))
