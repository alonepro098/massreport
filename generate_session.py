import sys
import asyncio

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from telethon import TelegramClient
from telethon.sessions import StringSession
from config import Config

async def main():
    print("==================================================")
    print("       Telegram Telethon StringSession Generator   ")
    print("==================================================")
    
    api_id = Config.API_ID
    api_hash = Config.API_HASH
    
    if not api_id or not api_hash:
        api_id_str = input("Enter your Telegram API_ID (from my.telegram.org): ").strip()
        api_hash = input("Enter your Telegram API_HASH: ").strip()
        if not api_id_str.isdigit():
            print("❌ Invalid API_ID!")
            return
        api_id = int(api_id_str)

    print("\nConnecting to Telegram servers...")
    client = TelegramClient(StringSession(), api_id, api_hash)
    await client.start()
    
    session_string = client.session.save()
    me = await client.get_me()
    
    print("\n✅ Authentication Successful!")
    print(f"User: {me.first_name} (@{me.username}) | ID: {me.id}")
    print("\n🔑 YOUR TELETHON STRING SESSION (Keep this private!):\n")
    print("--------------------------------------------------------------------------------")
    print(session_string)
    print("--------------------------------------------------------------------------------\n")
    print("Copy the string session above and paste it in your Bot under Session Manager!")
    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
