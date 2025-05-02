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
RUN chmod +x start.sh run_bot.py admin_panel.py

# Expose port for admin panel
EXPOSE 8080

# Run the setup script and start both applications
CMD ["./start.sh"] 