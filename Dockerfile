# ビルドステージ
FROM python:3.10-slim AS builder

# Python依存ライブラリのインストール(本番イメージにpipは含めない)
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
    && pip uninstall -y pip setuptools wheel

# 本番ステージ
FROM python:3.10-slim

# Chromiumとドライバのみ(chromiumの依存で必要なlibは自動で入る)
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        chromium \
        chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# ビルドステージから必要なファイルをコピー
COPY --from=builder /usr/local/lib/python3.10/site-packages /usr/local/lib/python3.10/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# 本番ではpip/setuptools/wheelは不要(ベースイメージ分も除去)
RUN find /usr/local/lib/python3.10/site-packages -maxdepth 1 \
      \( -name 'pip' -o -name 'pip-*' -o -name 'setuptools' -o -name 'setuptools-*' -o -name 'wheel' -o -name 'wheel-*' \) \
      -exec rm -rf {} + \
    && rm -f /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.10

# アプリケーションコードのコピー
COPY app/ /app/src/
WORKDIR /app/src

# 環境変数の設定
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium

# 実行
CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--timeout", "120", "--log-level=debug", "app:app"]
