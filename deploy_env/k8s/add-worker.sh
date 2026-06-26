#!/bin/bash
# masterノードで実行する
# 新しいworkerノードに渡すjoinコマンドを生成する（k3s用）
set -e

MASTER_IP="${1:-}"

if [ -z "$MASTER_IP" ]; then
  echo "使い方: bash add-worker.sh <masterの追加ネットワークIP>"
  echo "  例:  bash add-worker.sh 10.10.10.208"
  exit 1
fi

TOKEN=$(cat /var/lib/rancher/k3s/server/node-token)

echo "【新しいVPSで以下を実行してください】"
echo ""
echo "curl -sfL https://get.k3s.io | K3S_URL=https://${MASTER_IP}:6443 K3S_TOKEN=${TOKEN} sh -"
echo ""
echo "【参加確認（masterで）】"
echo "kubectl get nodes"
