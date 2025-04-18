FROM python:3.10-slim

# OSパッケージとChrome関連のインストール
RUN apt-get update && apt-get install -y \
    chromium chromium-driver wget curl unzip gnupg2 \
    libnss3 libxss1 libgconf-2-4 libasound2 libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

ENV CHROME_BIN=/usr/bin/chromium

# Python依存ライブラリ
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 作業ディレクトリ設定
WORKDIR /app/src

ENV PYTHONUNBUFFERED=1

# スクリプトとログインファイルを後からマウントするのでCOPYは不要

# 実行
# CMD ["python", "main.py"]
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--log-level=debug", "app:app"]
