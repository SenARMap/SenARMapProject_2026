#!/bin/bash
# workerノードで実行するスクリプト（k3s用）
# masterノードのIPとトークンが必要
# masterで「bash add-worker.sh <masterIP>」を実行してコマンドを取得してください
set -e

MASTER_IP="${1:-}"
TOKEN="${2:-}"

if [ -z "$MASTER_IP" ] || [ -z "$TOKEN" ]; then
  echo "使い方: bash setup-node.sh <masterIP> <token>"
  echo ""
  echo "masterノードで以下を実行してコマンドを取得してください:"
  echo "  bash add-worker.sh <masterのプライベートIP>"
  exit 1
fi

echo "==> [1/2] スワップを無効化（K8s必須要件）..."
sudo swapoff -a
sudo sed -i '/swap/d' /etc/fstab

echo "==> [2/2] k3s agentをインストールしてクラスターに参加..."
curl -sfL https://get.k3s.io | \
  K3S_URL="https://${MASTER_IP}:6443" \
  K3S_TOKEN="${TOKEN}" \
  sh -

echo ""
echo "=================================================="
echo "workerノードがクラスターに参加しました！"
echo "masterで確認: kubectl get nodes"
echo "=================================================="
