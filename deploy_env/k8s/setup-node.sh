#!/bin/bash
# 全ノード（master / worker 共通）で実行するスクリプト
# ConoHa VPS Ubuntu 想定
set -e

echo "==> [1/5] スワップを無効化（K8s必須要件）..."
sudo swapoff -a
sudo sed -i '/swap/d' /etc/fstab

echo "==> [2/5] カーネルモジュールとネットワーク設定..."
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF
sudo modprobe overlay
sudo modprobe br_netfilter

cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF
sudo sysctl --system

echo "==> [3/5] containerd インストール..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
  -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF

sudo apt-get update
sudo apt-get install -y containerd.io

# containerd のデフォルト設定を生成して SystemdCgroup を有効化
sudo mkdir -p /etc/containerd
containerd config default | sudo tee /etc/containerd/config.toml > /dev/null
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/' /etc/containerd/config.toml
sudo systemctl restart containerd
sudo systemctl enable containerd

echo "==> [4/5] kubeadm / kubelet / kubectl インストール..."
sudo apt-get install -y apt-transport-https
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.31/deb/Release.key \
  | sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.31/deb/ /' \
  | sudo tee /etc/apt/sources.list.d/kubernetes.list

sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl
sudo apt-mark hold kubelet kubeadm kubectl
sudo systemctl enable kubelet

echo "==> [5/5] プロダクション警告を設定..."
PROMPT_SETTING='export PS1="\[\e[41;1;37m\][PRODUCTION/K8s] \u@\h:\w $ \[\e[0m\] "'
if ! grep -q "\[PRODUCTION/K8s\]" ~/.bashrc; then
  echo "$PROMPT_SETTING" >> ~/.bashrc
fi

echo ""
echo "=================================================="
echo "ノードセットアップ完了！"
echo ""
echo "【masterノードの場合】"
echo "  sudo bash setup-master.sh"
echo ""
echo "【workerノードの場合】"
echo "  masterで出力された kubeadm join コマンドを実行してください"
echo "=================================================="
