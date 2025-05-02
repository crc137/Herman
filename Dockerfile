FROM python:3.9-slim

WORKDIR /app

# Install supervisor
RUN apt-get update && apt-get install -y supervisor && apt-get clean

# Copy requirements first to leverage Docker cache
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy all application files
COPY . .

# Make scripts executable
RUN chmod +x start.sh run_telegram_bot.sh launch_both.sh

# Copy supervisor configuration
COPY supervisor.conf /etc/supervisor/conf.d/herman.conf

# Use supervisor to manage both processes
CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/herman.conf"] 