FROM python:3.11-slim

# Install system dependencies for Playwright
RUN apt-get update && apt-get install -y \
    wget gnupg libgconf-2-4 libatk1.0-0 libatk-bridge2.0-0 \
    libgdk-pixbuf2.0-0 libgtk-3-0 libgbm1 libnss3 libxss1 \
    libasound2 libxtst6 libxrandr2 libxcomposite1 libxcursor1 \
    libxdamage1 libxi6 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium
RUN playwright install-deps chromium

COPY main.py .
COPY src/ ./src/
COPY config/ ./config/

ENV PYTHONUNBUFFERED=1
ENV PLAYWRIGHT_BROWSERS_PATH=/root/.cache/ms-playwright

CMD ["python", "-m", "functions_framework", "--target", "main", "--port", "8080"]
