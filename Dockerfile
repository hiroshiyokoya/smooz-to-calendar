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

# スクリプトとログインファイルを後からマウントするのでCOPYは不要

# 実行
CMD ["python", "main.py"]

# FROM python:3.10-slim

# # OSパッケージ & Chromeインストール
# RUN apt-get update && apt-get install -y \
#     chromium chromium-driver wget curl unzip gnupg2 \
#     libnss3 libxss1 libgconf-2-4 libasound2 libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 fonts-liberation \
#     && rm -rf /var/lib/apt/lists/*

# ENV CHROME_BIN=/usr/bin/chromium

# # 必要ライブラリ
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # スクリプト
# COPY script.py .
# COPY login.txt .

# CMD ["python", "script.py"]
