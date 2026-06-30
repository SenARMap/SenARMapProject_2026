#!/usr/bin/env bash
#
# 04-join-worker.sh
#   worker(node2) のみで実行。
#   kubelet の node-ip をローカルIPに固定してから、03 が出力した join コマンドを実行する。
#
#   使い方:
#     sudo ./04-join-worker.sh 'kubeadm join 192.168.0.11:6443 --token xxxx \
#         --discovery-token-ca-cert-hash sha256:yyyy'
#   (03-init-master.sh が表示した join コマンドを丸ごと ' ' で囲んで渡す)
#
set -euo pipefail
if [ "$(id -u)" -ne 0 ]; then echo "root で実行してください (sudo)"; exit 1; fi

JOIN_CMD="${1:-}"
if [ -z "$JOIN_CMD" ]; then
  echo "引数に join コマンドを渡してください。例:"
  echo "  sudo $0 'kubeadm join 192.168.0.11:6443 --token ... --discovery-token-ca-cert-hash sha256:...'"
  exit 1
fi

# ローカル側 NIC / IP を特定
PUB_IF="$(ip route show default | awk '{print $5; exit}')"
PRIV_IF=""
for i in $(ls /sys/class/net); do
  case "$i" in lo|"$PUB_IF") continue ;; esac
  if [[ "$i" =~ ^(eth|ens|enp) ]]; then PRIV_IF="$i"; break; fi
done
[ -n "$PRIV_IF" ] || { echo "ローカルNICが見つかりません。01-localnet.sh を先に実行してください"; exit 1; }
PRIV_IP="$(ip -4 -o addr show "$PRIV_IF" | awk '{print $4}' | cut -d/ -f1 | head -n1)"
[ -n "$PRIV_IP" ] || { echo "ローカルIPが未設定です。01-localnet.sh を先に実行してください"; exit 1; }
echo "ローカルIP(${PRIV_IF})=${PRIV_IP}"

echo "=== kubelet の node-ip をローカルIPに固定 ==="
echo "KUBELET_EXTRA_ARGS=--node-ip=${PRIV_IP}" > /etc/default/kubelet
systemctl daemon-reload || true

echo "=== クラスタに参加 ==="
eval "${JOIN_CMD}"

echo "完了。control-plane 側で kubectl get nodes を実行し Ready を確認してください。"
