#!/bin/bash
# Скрипт для запуска телеграм-бота и админ-панели в одном окне

# Перейти в директорию приложения
cd /app/Herman || cd Herman

# Вывести текущий каталог для диагностики
echo "Running from directory: $(pwd)"

# Setup env file first
echo "Setting up .env file..."
python setup_env.py

# Создаем временные файлы для логов
BOT_LOG=$(mktemp)
ADMIN_LOG=$(mktemp)

echo "Bot logs will be in: $BOT_LOG"
echo "Admin panel logs will be in: $ADMIN_LOG"

# Запускаем бота в одном терминале, перенаправляя вывод в файл
echo "Starting Telegram bot..."
(python run_bot.py > $BOT_LOG 2>&1) &
BOT_PID=$!
echo "Bot started with PID: $BOT_PID"

# Запускаем админ-панель с перенаправлением в другой файл
echo "Starting admin panel..."
(python admin_panel.py > $ADMIN_LOG 2>&1) &
ADMIN_PID=$!
echo "Admin panel started with PID: $ADMIN_PID"

# Функция для отображения логов в режиме реального времени
function show_logs() {
    echo "=== Telegram Bot Logs ==="
    tail -f $BOT_LOG &
    TAIL1_PID=$!
    
    echo "=== Admin Panel Logs ==="
    tail -f $ADMIN_LOG &
    TAIL2_PID=$!
    
    # Ожидание нажатия Ctrl+C
    trap "kill $TAIL1_PID $TAIL2_PID $BOT_PID $ADMIN_PID; exit" INT
    wait
}

# Показываем логи
show_logs 