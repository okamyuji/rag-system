FROM python:3.13-slim

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 3.13対応: piptools, setuptools, wheel, setuptools-rustを最新版に更新
RUN pip install --upgrade pip setuptools==75.6.0 wheel setuptools-rust

# Python 3.13互換性の環境変数設定
ENV PIP_NO_BUILD_ISOLATION=0
ENV PIP_USE_PEP517=1

# Pythonの依存関係をインストール（バイナリのみ使用を試行）
COPY requirements.txt .
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# アプリケーションのソースコードをコピー
COPY . .

EXPOSE 8000

CMD ["python", "app.py"]
