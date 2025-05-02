#!/bin/bash
# Скрипт для запуска телеграм-бота и админ-панели

# Вывести текущий каталог для диагностики
echo "Running from directory: $(pwd)"

# Создать .env файл из переменных окружения
echo "Setting up .env file..."
python setup_env.py

# Запускаем бота и админ-панель
echo "Starting services..."
python run_bot.py &
BOT_PID=$!

echo "Starting admin panel..."
python admin_panel.py &
ADMIN_PID=$!

# Ловим сигналы для корректного завершения
trap "kill $BOT_PID $ADMIN_PID; exit" SIGINT SIGTERM

# Ждём завершения любого из процессов
wait $BOT_PID $ADMIN_PID 