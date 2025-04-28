#!/bin/bash

# 設定
PROJECT_ID=$(gcloud config get-value project)  # 現在のプロジェクトIDを取得
REGION=$(gcloud config get-value compute/region)  # 現在のリージョンを取得
if [ -z "$REGION" ]; then
  REGION="asia-northeast1"  # リージョンが設定されていない場合は東京リージョンを使用
fi
SERVICE_NAME="smooz-runner"     # サービス名
IMAGE_NAME="gcr.io/${PROJECT_ID}/${SERVICE_NAME}"

# エラー時にスクリプトを停止
set -e

echo "🚀 Smooz Sync のデプロイを開始します..."
echo "📋 プロジェクト: ${PROJECT_ID}"
echo "🌍 リージョン: ${REGION}"

# 必要なAPIを有効化
echo "🔌 必要なAPIを有効化します..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# イメージをビルドしてGCPにpush
echo "🏗️ イメージをビルドしてGCPにpushします..."
gcloud builds submit --tag ${IMAGE_NAME}

# Cloud Runにデプロイ
echo "🚀 Cloud Runにデプロイします..."
gcloud run deploy ${SERVICE_NAME} \
  --image ${IMAGE_NAME} \
  --platform managed \
  --region ${REGION} \
  --memory 1Gi \
  --allow-unauthenticated \
  --set-env-vars="PYTHONUNBUFFERED=1"

# 古いイメージを削除
echo "🧹 古いイメージを削除します..."
# latestタグ以外のイメージを削除
gcloud container images list-tags ${IMAGE_NAME} \
  --filter="NOT tags:latest" \
  --format="get(digest)" | \
  while read digest; do
    if [ ! -z "$digest" ]; then
      echo "  削除: ${IMAGE_NAME}@${digest}"
      gcloud container images delete "${IMAGE_NAME}@${digest}" --quiet
    fi
  done

echo "✅ デプロイが完了しました！"
echo "🌐 サービスのURL: $(gcloud run services describe ${SERVICE_NAME} --region ${REGION} --format 'value(status.url)')"