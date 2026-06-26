#!/bin/bash
# masterノードのみで実行するスクリプト
# setup-node.sh を実行した後に実行すること
set -e

# ConoHaの追加ネットワーク側のIPアドレスを指定する
# 例: ip a で表示される 192.168.xxx.xxx のアドレス
PRIVATE_IP="${1:-}"

if [ -z "$PRIVATE_IP" ]; then
  echo "使い方: sudo bash setup-master.sh <追加ネットワークのIP>"
  echo "  例:  sudo bash setup-master.sh 192.168.100.10"
  echo ""
  echo "IPアドレスは以下のコマンドで確認できます:"
  echo "  ip a"
  exit 1
fi

echo "==> [1/3] K8sクラスターを初期化します (API endpoint: ${PRIVATE_IP})..."
sudo kubeadm init \
  --apiserver-advertise-address="${PRIVATE_IP}" \
  --pod-network-cidr=10.244.0.0/16

echo "==> [2/3] kubectl の設定..."
mkdir -p "$HOME/.kube"
sudo cp /etc/kubernetes/admin.conf "$HOME/.kube/config"
sudo chown "$(id -u):$(id -g)" "$HOME/.kube/config"

echo "==> [3/3] CNIプラグイン（Flannel）インストール..."
# Flannel がノード間のパケット転送を担う
kubectl apply -f \
  https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml

echo ""
echo "=================================================="
echo "masterセットアップ完了！"
echo ""
echo "ノードの状態確認（Readyになるまで1〜2分かかります）:"
echo "  kubectl get nodes"
echo ""
echo "【workerノードの追加方法】"
echo "  以下のコマンドを各workerノードで実行してください:"
kubeadm token create --print-join-command
echo ""
echo "【アプリのデプロイ】"
echo "  secrets.yaml を作成してから:"
echo "  bash deploy.sh"
echo "=================================================="
