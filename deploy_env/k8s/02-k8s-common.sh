#!/usr/bin/env bash
#
# 02-k8s-common.sh
#   Kubernetes ノード共通のセットアップ。
#   control-plane / worker の両方で、そのまま実行する(編集不要)。
#   server-world (Ubuntu 24.04 / Kubernetes) の手順に準拠 + containerd 利用。
#
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "root で実行してください (sudo)"; exit 1; fi

K8S_MINOR="v1.36"   # 2026年時点の安定版。揃えたい場合は両ノードで同じ値に。

echo "=== 1. swap 無効化 ==="
swapoff -a || true
sed -i.bak -E '/\sswap\s/ s/^/#/' /etc/fstab || true

echo "=== 2. カーネルモジュール (overlay, br_netfilter) ==="
cat > /etc/modules-load.d/k8s.conf <<EOF
overlay
br_netfilter
EOF
modprobe overlay
modprobe br_netfilter

echo "=== 3. sysctl (ブリッジ/フォワーディング) ==="
cat > /etc/sysctl.d/k8s.conf <<EOF
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sysctl --system >/dev/null

echo "=== 4. containerd インストール & SystemdCgroup 有効化 ==="
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y containerd apt-transport-https ca-certificates curl gpg
mkdir -p /etc/containerd
containerd config default | tee /etc/containerd/config.toml >/dev/null
sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
systemctl restart containerd
systemctl enable containerd

echo "=== 5. Kubernetes リポジトリ追加 (${K8S_MINOR}) ==="
mkdir -p /etc/apt/keyrings
curl -fsSL "https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/Release.key" \
  | gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo "deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/${K8S_MINOR}/deb/ /" \
  > /etc/apt/sources.list.d/kubernetes.list

echo "=== 6. kubelet / kubeadm / kubectl インストール ==="
apt-get update
apt-get install -y kubelet kubeadm kubectl
apt-mark hold kubelet kubeadm kubectl
systemctl enable kubelet

echo "完了。次は control-plane で 03-init-master.sh、worker で 04-join-worker.sh を実行してください。"
