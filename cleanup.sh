#!/bin/bash

# Cloud Runの古いリビジョンと、対応するArtifact Registryのイメージを掃除する。
# 2025以降はContainer Registry(gcr.io)が終了しているため、gcloud container images系ではなくArtifact Registryを使う。

set -euo pipefail

PROJECT_ID="$(gcloud config get-value project)"
REGION="$(gcloud config get-value run/region)"
if [ -z "$REGION" ] || [ "$REGION" = "(unset)" ]; then
  REGION="asia-northeast1"
fi

SERVICE_NAME="${SERVICE_NAME:-smooz-runner}"
KEEP_REVISIONS="${KEEP_REVISIONS:-10}"

echo "🧹 クリーンアップ開始"
echo "📋 プロジェクト: ${PROJECT_ID}"
echo "🌍 リージョン: ${REGION}"
echo "🛰️ サービス: ${SERVICE_NAME}"
echo "📌 保持するリビジョン数: ${KEEP_REVISIONS}"

traffic_revisions="$(gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" --format='value(status.traffic.revisionName)' | tr '\n' ' ')"
echo "🚦 トラフィックが流れているリビジョン: ${traffic_revisions:-(なし)}"

revisions="$(
  gcloud run revisions list \
    --service "${SERVICE_NAME}" \
    --region "${REGION}" \
    --sort-by="~metadata.creationTimestamp" \
    --format="value(metadata.name)"
)"

if [ -z "${revisions}" ]; then
  echo "ℹ️ リビジョンが見つかりませんでした"
  exit 0
fi

keep=0
deleted=0

while IFS= read -r rev; do
  if [ -z "${rev}" ]; then
    continue
  fi

  if echo " ${traffic_revisions} " | grep -q " ${rev} "; then
    echo "⏭️ スキップ(トラフィックあり): ${rev}"
    continue
  fi

  if [ "${keep}" -lt "${KEEP_REVISIONS}" ]; then
    echo "✅ 保持: ${rev}"
    keep=$((keep + 1))
    continue
  fi

  image="$(gcloud run revisions describe "${rev}" --region "${REGION}" --format='value(spec.containers[0].image)' || true)"
  echo "🗑️ 削除: ${rev}"
  gcloud run revisions delete "${rev}" --region "${REGION}" --quiet
  deleted=$((deleted + 1))

  # リビジョンの参照先イメージも掃除(存在しない/権限不足は無視)
  if [ -n "${image}" ]; then
    echo "🧽 イメージ削除を試行: ${image}"
    gcloud artifacts docker images delete "${image}" --delete-tags --quiet || true
  fi
done <<< "${revisions}"

echo "✅ クリーンアップ完了(削除リビジョン数: ${deleted})"

