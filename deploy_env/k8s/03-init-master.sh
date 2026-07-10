#!/usr/bin/env bash
#
# 03-init-master.sh
#   control-plane(node1) のみで実行。
#   - kubelet がローカルネットワークIPを名乗るよう --node-ip を固定
#   - kubeadm init (API Server はローカルIPで待ち受け / 証明書には公開IPも追加)
#   - Flannel CNI を導入し、VXLAN をローカルネットワーク(eth1)に固定
#   - worker 用の join コマンドを表示
#
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "root で実行してください (sudo)"; exit 1; fi

POD_CIDR="10.244.0.0/16"   # Flannel 既定。変更不要。

# 公開側 / ローカル側インターフェイスとIPを特定
PUB_IF="$(ip route show default | awk '{print $5; exit}')"
PRIV_IF=""
for i in $(ls /sys/class/net); do
  case "$i" in lo|"$PUB_IF") continue ;; esac
  if [[ "$i" =~ ^(eth|ens|enp) ]]; then PRIV_IF="$i"; break; fi
done
[ -n "$PRIV_IF" ] || { echo "ローカルNICが見つかりません。01-localnet.sh を先に実行してください"; exit 1; }

PRIV_IP="$(ip -4 -o addr show "$PRIV_IF" | awk '{print $4}' | cut -d/ -f1 | head -n1)"
PUB_IP="$(ip -4 -o addr show "$PUB_IF" | awk '{print $4}' | cut -d/ -f1 | head -n1)"
[ -n "$PRIV_IP" ] || { echo "ローカルIPが未設定です。01-localnet.sh を先に実行してください"; exit 1; }
echo "ローカルIP(${PRIV_IF})=${PRIV_IP} / 公開IP(${PUB_IF})=${PUB_IP}"

echo "=== kubelet の node-ip をローカルIPに固定 ==="
echo "KUBELET_EXTRA_ARGS=--node-ip=${PRIV_IP}" > /etc/default/kubelet
systemctl daemon-reload || true

echo "=== kubeadm init ==="
kubeadm init \
  --apiserver-advertise-address="${PRIV_IP}" \
  --apiserver-cert-extra-sans="${PUB_IP}" \
  --pod-network-cidr="${POD_CIDR}"

echo "=== kubeconfig 配置 (root 用) ==="
mkdir -p "$HOME/.kube"
cp -f /etc/kubernetes/admin.conf "$HOME/.kube/config"
chown "$(id -u):$(id -g)" "$HOME/.kube/config"
export KUBECONFIG="$HOME/.kube/config"

# sudo を呼んだ実ユーザー側にも配置(任意)
if [ -n "${SUDO_USER:-}" ] && [ "${SUDO_USER}" != "root" ]; then
  U_HOME="$(eval echo "~${SUDO_USER}")"
  mkdir -p "${U_HOME}/.kube"
  cp -f /etc/kubernetes/admin.conf "${U_HOME}/.kube/config"
  chown -R "${SUDO_USER}:${SUDO_USER}" "${U_HOME}/.kube"
fi

echo "=== Flannel CNI 導入 ==="
curl -fsSL -o /tmp/kube-flannel.yml \
  https://github.com/flannel-io/flannel/releases/latest/download/kube-flannel.yml
kubectl apply -f /tmp/kube-flannel.yml
# VXLAN をローカルネットワーク側 NIC に固定
kubectl -n kube-flannel patch ds kube-flannel-ds --type=json \
  -p="[{\"op\":\"add\",\"path\":\"/spec/template/spec/containers/0/args/-\",\"value\":\"--iface=${PRIV_IF}\"}]"

echo
echo "=================================================================="
echo " worker(node2) で実行する join コマンド:"
echo "   ※ 先に node2 で /etc/default/kubelet に node-ip を設定すること"
echo "------------------------------------------------------------------"
kubeadm token create --print-join-command
echo "=================================================================="
echo
echo "確認: kubectl get nodes  /  kubectl get pods -A"
