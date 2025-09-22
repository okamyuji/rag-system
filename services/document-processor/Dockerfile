FROM python:3.13-slim

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    libreoffice \
    poppler-utils \
    tesseract-ocr \
    tesseract-ocr-jpn \
    tesseract-ocr-eng \
    wget \
    libgl1 \
    libglib2.0-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* \
    && rm -rf /var/cache/apt/archives/*

WORKDIR /app

# Pythonの依存関係をインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

# 必要なディレクトリを作成
RUN mkdir -p /app/uploads /app/processed

EXPOSE 8001

CMD ["python", "app.py"]
