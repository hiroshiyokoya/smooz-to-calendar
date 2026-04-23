#!/bin/bash

# 設定
PROJECT_ID="$(gcloud config get-value project)"  # 現在のプロジェクトIDを取得
REGION="$(gcloud config get-value run/region)"   # Cloud Runのデフォルトリージョンを取得
if [ -z "$REGION" ] || [ "$REGION" = "(unset)" ]; then
  REGION="asia-northeast1"  # リージョンが設定されていない場合は東京リージョンを使用
fi
SERVICE_NAME="smooz-runner"    # Cloud Runのサービス名
AR_REPOSITORY="smooz-sync"     # Artifact Registryのリポジトリ名
IMAGE_BASE="${REGION}-docker.pkg.dev/${PROJECT_ID}/${AR_REPOSITORY}/${SERVICE_NAME}"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
IMAGE_NAME="${IMAGE_BASE}:${IMAGE_TAG}"

# エラー時にスクリプトを停止
set -e

echo "🚀 Smooz Sync のデプロイを開始します..."
echo "📋 プロジェクト: ${PROJECT_ID}"
echo "🌍 リージョン: ${REGION}"
echo "📦 Artifact Registry: ${AR_REPOSITORY}"
echo "🐳 イメージ: ${IMAGE_NAME}"

# 必要なAPIを有効化
echo "🔌 必要なAPIを有効化します..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com

# Artifact Registryリポジトリを作成(存在しない場合)
if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" --location "${REGION}" >/dev/null 2>&1; then
  echo "🧱 Artifact Registryリポジトリを作成します..."
  gcloud artifacts repositories create "${AR_REPOSITORY}" \
    --repository-format docker \
    --location "${REGION}" \
    --description "Smooz Sync container images"
fi

# イメージをビルドしてArtifact Registryへpush
echo "🏗️ イメージをビルドしてArtifact Registryへpushします..."
gcloud builds submit --tag "${IMAGE_NAME}"

# latestタグを付け直す(運用しやすさのため)
echo "🏷️ latestタグを更新します..."
gcloud artifacts docker tags add "${IMAGE_NAME}" "${IMAGE_BASE}:latest" --quiet

# Cloud Runにデプロイ
echo "🚀 Cloud Runにデプロイします..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --platform managed \
  --region "${REGION}" \
  --memory 1Gi \
  --allow-unauthenticated \
  --set-env-vars="PYTHONUNBUFFERED=1"

echo "✅ デプロイが完了しました！"
echo "🌐 サービスのURL: $(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format 'value(status.url)')"
echo "🧹 クリーンアップは ./cleanup.sh を実行してください"
