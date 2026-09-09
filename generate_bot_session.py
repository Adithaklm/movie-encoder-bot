"""Generate a Telethon StringSession for the bot account.

Run this script LOCALLY, not on Koyeb. It does not create or store a .session file.
The generated string should be copied directly into Koyeb as BOT_SESSION_STRING.
"""

import asyncio
import getpass

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main():
    print("=== Telegram Bot StringSession Generator ===")
    print("Run this on your own computer. Never publish the generated session string.\n")

    api_id = int(input("API ID: ").strip())
    api_hash = getpass.getpass("API HASH: ").strip()
    bot_token = getpass.getpass("BOT TOKEN: ").strip()

    client = TelegramClient(StringSession(), api_id, api_hash)
    try:
        await client.start(bot_token=bot_token)
        session_string = client.session.save()
        me = await client.get_me()

        print("\nBot authenticated successfully.")
        print(f"Bot: @{me.username or 'unknown'}")
        print("\nBOT_SESSION_STRING:")
        print(session_string)
        print("\nCopy the value above to your Koyeb environment variable:")
        print("BOT_SESSION_STRING=<generated value>")
        print("\nIMPORTANT: Treat this session string like a password.")
        print("Do not commit it to GitHub or send it in chat.")
    finally:
        await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
