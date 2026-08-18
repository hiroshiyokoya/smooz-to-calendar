#!/bin/bash

# Cloud Runの古いリビジョンと、Artifact Registryの未参照イメージを掃除する。
# GCPプロジェクトIDは公開リポジトリに書かない。ローカルの .gcp.env か環境変数で渡す。

set -euo pipefail

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

SERVICE_NAME="${SERVICE_NAME:-smooz-runner}"
AR_REPOSITORY="${AR_REPOSITORY:-smooz-sync}"
IMAGE_BASE="${REGION}-docker.pkg.dev/${GCP_PROJECT_ID}/${AR_REPOSITORY}/${SERVICE_NAME}"

KEEP_REVISIONS="${KEEP_REVISIONS:-1}"
KEEP_IMAGE_TAGS="${KEEP_IMAGE_TAGS:-0}"

echo "🧹 クリーンアップ開始"
echo "📋 プロジェクト: ${GCP_PROJECT_ID}"
echo "🌍 リージョン: ${REGION}"
echo "🛰️ サービス: ${SERVICE_NAME}"
echo "📦 イメージ: ${IMAGE_BASE}"
echo "📌 保持する旧リビジョン数(非トラフィック): ${KEEP_REVISIONS}"
echo "📌 保持する未参照イメージ数: ${KEEP_IMAGE_TAGS}"

traffic_revisions="$(
  gcloud run services describe "${SERVICE_NAME}" --region "${REGION}" \
    --format='value(status.traffic.revisionName)' "${GCLOUD_PROJECT[@]}" | tr '\n' ' '
)"
echo "🚦 トラフィックが流れているリビジョン: ${traffic_revisions:-(なし)}"

revisions="$(
  gcloud run revisions list \
    --service "${SERVICE_NAME}" \
    --region "${REGION}" \
    --sort-by="~metadata.creationTimestamp" \
    --format="value(metadata.name)" \
    "${GCLOUD_PROJECT[@]}"
)"

deleted_revisions=0
if [ -n "${revisions}" ]; then
  keep=0
  while IFS= read -r rev; do
    if [ -z "${rev}" ]; then
      continue
    fi

    if echo " ${traffic_revisions} " | grep -q " ${rev} "; then
      echo "⏭️ スキップ(トラフィックあり): ${rev}"
      continue
    fi

    if [ "${keep}" -lt "${KEEP_REVISIONS}" ]; then
      echo "✅ リビジョン保持: ${rev}"
      keep=$((keep + 1))
      continue
    fi

    echo "🗑️ リビジョン削除: ${rev}"
    gcloud run revisions delete "${rev}" --region "${REGION}" --quiet "${GCLOUD_PROJECT[@]}"
    deleted_revisions=$((deleted_revisions + 1))
  done <<< "${revisions}"
else
  echo "ℹ️ リビジョンが見つかりませんでした"
fi

echo ""
echo "=== Artifact Registry の古いイメージ整理 ==="

protected_digests="$(
  gcloud run revisions list \
    --service "${SERVICE_NAME}" \
    --region "${REGION}" \
    --format='value(spec.containers[0].image)' \
    "${GCLOUD_PROJECT[@]}" \
  | sed -n 's/.*@//p' \
  | sort -u
)"

if [ -z "${protected_digests}" ]; then
  echo "ℹ️ 保護対象のdigestがありません(リビジョン未検出)"
else
  echo "🔒 保護するdigest(稼働中リビジョン):"
  echo "${protected_digests}" | sed 's/^/  /'
fi

mapfile -t image_lines < <(
  gcloud artifacts docker images list "${IMAGE_BASE}" \
    --include-tags \
    --format='value(version,createTime,tags)' \
    --sort-by=~create_time \
    "${GCLOUD_PROJECT[@]}"
)

deleted_images=0
if [ "${#image_lines[@]}" -eq 0 ]; then
  echo "ℹ️ ${IMAGE_BASE} にイメージがありません"
else
  orphan_kept=0
  for line in "${image_lines[@]}"; do
    digest="${line%%$'\t'*}"
    rest="${line#*$'\t'}"
    tags="${rest#*$'\t'}"

    if echo "${protected_digests}" | grep -qx "${digest}"; then
      echo "🔒 保持(稼働中): ${digest} [${tags}]"
      continue
    fi

    if [ "${orphan_kept}" -lt "${KEEP_IMAGE_TAGS}" ]; then
      echo "✅ 未参照イメージを保持: ${digest} [${tags}]"
      orphan_kept=$((orphan_kept + 1))
      continue
    fi

    ref="${IMAGE_BASE}"
    if [ -n "${tags}" ] && [ "${tags}" != "None" ]; then
      first_tag="${tags%%,*}"
      ref="${IMAGE_BASE}:${first_tag}"
    else
      ref="${IMAGE_BASE}@${digest}"
    fi

    echo "🗑️ イメージ削除: ${ref}"
    if gcloud artifacts docker images delete "${ref}" --delete-tags --quiet "${GCLOUD_PROJECT[@]}"; then
      deleted_images=$((deleted_images + 1))
    else
      echo "⚠️ 削除に失敗(権限または参照中): ${ref}"
    fi
  done
fi

if [ "${CLEANUP_LEGACY_GCR:-0}" = "1" ]; then
  echo ""
  echo "=== 旧 Container Registry (gcr.io) イメージの削除 ==="
  legacy_ref="gcr.io/${GCP_PROJECT_ID}/${SERVICE_NAME}"
  if gcloud container images describe "${legacy_ref}" "${GCLOUD_PROJECT[@]}" >/dev/null 2>&1; then
    echo "🗑️ 旧イメージ削除: ${legacy_ref}"
    gcloud container images delete "${legacy_ref}" --force-delete-tags --quiet "${GCLOUD_PROJECT[@]}" || true
  else
    echo "ℹ️ 旧イメージ ${legacy_ref} は見つかりませんでした"
  fi
fi

echo "✅ クリーンアップ完了(削除リビジョン数: ${deleted_revisions}, 削除イメージ数: ${deleted_images})"
