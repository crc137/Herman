#!/usr/bin/env python3
"""
Скрипт для запуска телеграм-бота и админ-панели
"""
import os
import sys
import signal
import subprocess
import time

def main():
    print("Running from directory:", os.getcwd())
    
    # Запуск setup_env.py для создания .env файла
    print("Setting up .env file...")
    try:
        subprocess.run([sys.executable, "setup_env.py"], check=True)
    except subprocess.CalledProcessError:
        print("Error setting up .env file")
        return 1
    
    # Запуск телеграм-бота
    print("Starting Telegram bot...")
    bot_process = subprocess.Popen([sys.executable, "run_bot.py"])
    
    # Запуск админ-панели
    print("Starting admin panel...")
    admin_process = subprocess.Popen([sys.executable, "admin_panel.py"])
    
    # Функция для корректного завершения процессов
    def signal_handler(sig, frame):
        print("Shutting down services...")
        bot_process.terminate()
        admin_process.terminate()
        sys.exit(0)
    
    # Обработка сигналов для корректного завершения
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    # Ждём завершения любого из процессов
    while bot_process.poll() is None and admin_process.poll() is None:
        time.sleep(1)
    
    # Если один из процессов завершился, завершаем другой
    if bot_process.poll() is not None:
        print("Bot process terminated with code:", bot_process.returncode)
        admin_process.terminate()
    else:
        print("Admin panel process terminated with code:", admin_process.returncode)
        bot_process.terminate()
    
    return 0

if __name__ == "__main__":
    sys.exit(main()) 