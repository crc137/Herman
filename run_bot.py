#!/usr/bin/env python3
import asyncio
from telegram_bot import TelegramBot

async def main():
    bot = TelegramBot()
    try:
        print("Starting Telegram bot...")
        await bot.start()
    except KeyboardInterrupt:
        print("Bot stopped by user")
    except Exception as e:
        print(f"Error in bot: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 