#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> [1/4] Namespace を作成します..."
kubectl apply -f namespace.yaml

echo "==> [2/4] Secrets を適用します..."
if [ ! -f "secrets.yaml" ]; then
    echo "ERROR: secrets.yaml が見つかりません。"
    echo "  secrets.yaml.template をコピーして値を入力してください:"
    echo "  cp secrets.yaml.template secrets.yaml"
    echo "  # secrets.yaml を編集して各値を base64 エンコードして入力"
    exit 1
fi
kubectl apply -f secrets.yaml

echo "==> [3/4] K8s マニフェストを適用します..."
kubectl apply -k .

echo "==> [4/4] デプロイ状況を確認します..."
kubectl rollout status deployment/python   -n iki-project
kubectl rollout status deployment/nginx    -n iki-project
kubectl rollout status deployment/counter  -n iki-project
kubectl rollout status statefulset/db      -n iki-project
kubectl rollout status deployment/prometheus -n iki-project
kubectl rollout status deployment/grafana  -n iki-project

echo ""
echo "=================================================="
echo "デプロイ完了！"
echo ""
echo "Pod 一覧:"
kubectl get pods -n iki-project
echo "=================================================="
