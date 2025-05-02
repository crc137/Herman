#!/usr/bin/env python3
from telethon import TelegramClient
from config import API_ID, API_HASH
import os
import sys

async def main():
    print("Создание файла сессии для Telegram бота...")
    print("Этот файл можно будет загрузить на сервер для запуска бота без повторной авторизации")
    print()
    
    # Check if session file already exists
    if os.path.exists("herman_session.session"):
        print("Файл сессии 'herman_session.session' уже существует.")
        overwrite = input("Перезаписать? (y/n): ").lower() == 'y'
        if not overwrite:
            print("Отмена. Выход.")
            return
    
    # Create the client and connect
    client = TelegramClient("herman_session", API_ID, API_HASH)
    
    try:
        # Start the client (this will prompt for phone number and code)
        await client.start()
        
        # Check if we're logged in
        if await client.is_user_authorized():
            me = await client.get_me()
            print(f"\nУспешно создан файл сессии для {me.first_name} (@{me.username}, ID: {me.id})")
            print("\nФайл 'herman_session.session' создан в текущей директории.")
            print("Скопируйте этот файл на сервер в директорию Herman/ для запуска бота без повторного ввода данных.")
        else:
            print("Что-то пошло не так. Авторизация не удалась.")
    finally:
        await client.disconnect()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main()) 