#!/bin/bash
# masterノードのみで実行するスクリプト
# setup-node.sh を実行した後に実行すること
set -e

PRIVATE_IP="${1:-}"

if [ -z "$PRIVATE_IP" ]; then
  echo "使い方: bash setup-master.sh <追加ネットワークのIP>"
  echo "  例:  bash setup-master.sh 10.10.10.208"
  echo ""
  echo "IPアドレスは「ip a」で eth1 のアドレスを確認してください"
  exit 1
fi

echo "==> [1/3] K8sクラスターを初期化します (API endpoint: ${PRIVATE_IP})..."
sudo kubeadm init \
  --apiserver-advertise-address="${PRIVATE_IP}" \
  --pod-network-cidr=10.244.0.0/16

echo "==> [2/3] kubectl の設定..."
# rootでも使えるように設定
mkdir -p /root/.kube
cp /etc/kubernetes/admin.conf /root/.kube/config

# project-prod ユーザーでも kubectl を使えるように設定
# 日常操作は project-prod で行うこと（rootは使わない）
if id "project-prod" &>/dev/null; then
  mkdir -p /home/project-prod/.kube
  cp /etc/kubernetes/admin.conf /home/project-prod/.kube/config
  chown -R project-prod:project-prod /home/project-prod/.kube
  echo "project-prod ユーザーにも kubectl を設定しました"
fi

echo "==> [3/3] CNIプラグイン（Calico）インストール..."
# Calico: Flannel と違い NetworkPolicy（Pod間の通信制限）に対応
kubectl create -f \
  https://raw.githubusercontent.com/projectcalico/calico/v3.28.0/manifests/tigera-operator.yaml

kubectl apply -f - <<EOF
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
      - name: default-ipv4-ippool
        cidr: 10.244.0.0/16
        encapsulation: VXLANCrossSubnet
        natOutgoing: Enabled
        nodeSelector: all()
---
apiVersion: operator.tigera.io/v1
kind: APIServer
metadata:
  name: default
spec: {}
EOF

echo ""
echo "=================================================="
echo "masterセットアップ完了！"
echo ""
echo "ノードのReady確認（1〜2分かかります）:"
echo "  kubectl get nodes"
echo ""
echo "workerを追加する場合:"
echo "  bash add-worker.sh"
echo "=================================================="
