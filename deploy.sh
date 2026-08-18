#!/bin/bash

# 設定
# GCPプロジェクトIDは公開リポジトリに書かない。ローカルの .gcp.env か環境変数で渡す。
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
if [ -z "${GCP_PROJECT_ID:-}" ] && [ -f "${SCRIPT_DIR}/.gcp.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "${SCRIPT_DIR}/.gcp.env"
  set +a
fi
if [ -z "${GCP_PROJECT_ID:-}" ]; then
  echo "GCP_PROJECT_ID が未設定です。"
  echo "cp .gcp.env.example .gcp.env してプロジェクトIDを記入するか、環境変数 GCP_PROJECT_ID を渡してください。"
  echo "プロジェクトIDの確認: gcloud projects list / gcloud config get-value project"
  exit 1
fi
GCLOUD_PROJECT=(--project="${GCP_PROJECT_ID}")

REGION="$(gcloud config get-value run/region "${GCLOUD_PROJECT[@]}" 2>/dev/null)" 
if [ -z "$REGION" ] || [ "$REGION" = "(unset)" ]; then
  REGION="asia-northeast1"
fi
SERVICE_NAME="smooz-runner"
AR_REPOSITORY="smooz-sync"
IMAGE_BASE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${SERVICE_NAME}"
IMAGE_TAG="$(date +%Y%m%d-%H%M%S)"
IMAGE_NAME="${IMAGE_BASE}:${IMAGE_TAG}"

set -e

echo "🚀 Smooz Sync のデプロイを開始します..."
echo "📋 プロジェクト: ${GCP_PROJECT_ID}"
echo "🌍 リージョン: ${REGION}"
echo "📦 Artifact Registry: ${AR_REPOSITORY}"
echo "🐳 イメージ: ${IMAGE_NAME}"

echo "🔌 必要なAPIを有効化します..."
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com \
  "${GCLOUD_PROJECT[@]}"

if ! gcloud artifacts repositories describe "${AR_REPOSITORY}" \
    --location "${REGION}" "${GCLOUD_PROJECT[@]}" >/dev/null 2>&1; then
  echo "🧱 Artifact Registryリポジトリを作成します..."
  gcloud artifacts repositories create "${AR_REPOSITORY}" \
    --repository-format docker \
    --location "${REGION}" \
    --description "Smooz Sync container images" \
    "${GCLOUD_PROJECT[@]}"
fi

echo "🏗️ イメージをビルドしてArtifact Registryへpushします..."
gcloud builds submit --tag "${IMAGE_NAME}" "${GCLOUD_PROJECT[@]}"

echo "🏷️ latestタグを更新します..."
gcloud artifacts docker tags add "${IMAGE_NAME}" "${IMAGE_BASE}:latest" --quiet \
  "${GCLOUD_PROJECT[@]}"

echo "🚀 Cloud Runにデプロイします..."
gcloud run deploy "${SERVICE_NAME}" \
  --image "${IMAGE_NAME}" \
  --platform managed \
  --region "${REGION}" \
  --memory 1Gi \
  --allow-unauthenticated \
  --set-env-vars="PYTHONUNBUFFERED=1" \
  "${GCLOUD_PROJECT[@]}"

SERVICE_URL="$(gcloud run services describe "${SERVICE_NAME}" \
  --region "${REGION}" \
  --format 'value(status.url)' \
  "${GCLOUD_PROJECT[@]}")"

echo "✅ デプロイが完了しました！"
echo "🌐 サービスのURL: ${SERVICE_URL}"
echo "📎 GASエディタの Config.CLOUD_RUN_URL に次を設定してください(リポジトリには書かない):"
echo "   ${SERVICE_URL}/fetch_and_update"

echo ""
echo "🧹 古いリビジョンとイメージをクリーンアップします..."
GCP_PROJECT_ID="${GCP_PROJECT_ID}" KEEP_REVISIONS="${KEEP_REVISIONS:-0}" KEEP_IMAGE_TAGS="${KEEP_IMAGE_TAGS:-0}" \
  "$(dirname "$0")/cleanup.sh"
