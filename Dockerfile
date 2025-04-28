# ビルドステージ
FROM python:3.10-slim as builder

# Python依存ライブラリのインストール
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# 本番ステージ
FROM python:3.10-slim

# Chrome関連の最小限のパッケージのみをインストール
RUN apt-get update && apt-get install -y \
    chromium chromium-driver \
    libnss3 libxss1 libgconf-2-4 libasound2 libatk-bridge2.0-0 libgtk-3-0 libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

# ビルドステージから必要なファイルをコピー
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# アプリケーションコードのコピー
COPY app/ /app/src/
WORKDIR /app/src

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium

# 実行
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--log-level=debug", "app:app"]
