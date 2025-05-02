#!/usr/bin/env python3
"""
Скрипт для запуска телеграм-бота и админ-панели
"""
import os
import sys
import signal
import subprocess
import time

def create_env_file():
    """Create .env file with necessary configuration from environment variables"""
    env_content = ""
    
    # Telegram API credentials
    env_content += "# Telegram API credentials\n"
    env_content += f"API_ID={os.environ.get('API_ID', '')}\n"
    env_content += f"API_HASH={os.environ.get('API_HASH', '')}\n\n"
    
    # Group and user IDs
    env_content += "# Group and user IDs\n"
    env_content += f"TARGET_GROUP={os.environ.get('TARGET_GROUP', '')}\n"
    env_content += f"ADMIN_ID={os.environ.get('ADMIN_ID', '')}\n"
    env_content += f"CHANNEL_ID={os.environ.get('CHANNEL_ID', '')}\n\n"
    
    # Source groups
    env_content += "# Source groups to monitor\n"
    env_content += f"SOURCE_GROUPS={os.environ.get('SOURCE_GROUPS', '')}\n\n"
    
    # Database configuration
    env_content += "# Database configuration\n"
    env_content += f"USE_POSTGRES={os.environ.get('USE_POSTGRES', '')}\n"
    env_content += f"POSTGRES_DSN={os.environ.get('POSTGRES_DSN', '')}\n"
    env_content += f"DB_FILE={os.environ.get('DB_FILE', 'users_database.db')}\n\n"
    
    # Flask configuration
    env_content += "# Flask configuration\n"
    env_content += f"SECRET_KEY={os.environ.get('SECRET_KEY', '')}\n\n"
    
    # Admin panel credentials
    env_content += "# Admin panel credentials\n"
    env_content += f"ADMIN_USERNAME={os.environ.get('ADMIN_USERNAME', '')}\n"
    env_content += f"ADMIN_PASSWORD={os.environ.get('ADMIN_PASSWORD', '')}\n\n"
    
    # API endpoint for CAS check
    env_content += "# API endpoint for CAS check\n"
    env_content += f"CAS_API_URL={os.environ.get('CAS_API_URL', '')}\n"
    
    with open('.env', 'w') as f:
        f.write(env_content)
    print("Created .env file with configuration from environment variables.")

def main():
    print("Running from directory:", os.getcwd())
    
    # Создаем .env файл напрямую из переменных окружения
    print("Setting up .env file from environment variables...")
    try:
        create_env_file()
    except Exception as e:
        print(f"Error setting up .env file: {e}")
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
