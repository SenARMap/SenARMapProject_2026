#!/bin/bash
# masterノードで実行するスクリプト（k3s用）
# すでにk3sが入っている場合は不要
set -e

echo "==> [1/2] スワップを無効化（K8s必須要件）..."
sudo swapoff -a
sudo sed -i '/swap/d' /etc/fstab

echo "==> [2/2] k3s（masterモード）をインストール..."
curl -sfL https://get.k3s.io | sh -

echo ""
echo "=================================================="
echo "k3s masterセットアップ完了！"
echo ""
echo "クラスター確認:"
echo "  kubectl get nodes"
echo ""
echo "workerノードを追加する場合:"
echo "  bash add-worker.sh <このサーバーの追加ネットワークIP>"
echo "=================================================="
