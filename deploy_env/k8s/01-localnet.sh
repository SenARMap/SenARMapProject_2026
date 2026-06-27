#!/usr/bin/env bash
#
# 01-localnet.sh
#   ConoHa の「ローカルネットワーク」用 NIC (eth1 相当) に静的IPを設定する。
#   両ノードでそれぞれ実行する。PRIV_IP / PREFIX だけ各ノードに合わせて書き換える。
#
#   事前に ConoHa コントロールパネルで:
#     1) ローカルネットワークを作成 (例: 192.168.0.0/24)
#     2) サーバーを停止 → ローカルネットワークにアタッチ → サーバー起動
#   ※ ConoHa のローカルネットワークは x.x.x.11〜x.x.x.254 が利用可能
#     (x.x.x.1〜10 は予約)。DHCP は無いので静的設定が必須。
#
set -euo pipefail

# ===== ここを各ノードで設定 =====
PRIV_IP="192.168.0.11"   # control-plane(node1)=.11 / worker(node2)=.12 など
PREFIX="24"
# ================================

if [ "$(id -u)" -ne 0 ]; then echo "root で実行してください (sudo)"; exit 1; fi

# 既定ルートを持つ(=公開側)インターフェイスを特定
PUB_IF="$(ip route show default | awk '{print $5; exit}')"
echo "公開側インターフェイス: ${PUB_IF}"

# 公開側でない最初の物理 ethernet を「ローカルネットワーク側」とみなす
PRIV_IF=""
for i in $(ls /sys/class/net); do
  case "$i" in lo|"$PUB_IF") continue ;; esac
  if [[ "$i" =~ ^(eth|ens|enp) ]]; then PRIV_IF="$i"; break; fi
done

if [ -z "$PRIV_IF" ]; then
  echo "ローカルネットワーク用 NIC が見つかりません。ConoHa 側でアタッチ済みか確認してください。"
  echo "現在の NIC 一覧:"; ip -br link
  exit 1
fi
echo "ローカルネットワーク側インターフェイス: ${PRIV_IF}"

cat > /etc/netplan/11-localnetwork.yaml <<EOF
network:
  version: 2
  ethernets:
    ${PRIV_IF}:
      dhcp4: false
      dhcp6: false
      addresses: [${PRIV_IP}/${PREFIX}]
EOF
chmod 600 /etc/netplan/11-localnetwork.yaml

netplan apply
sleep 2
echo "----- 設定結果 -----"
ip -4 addr show "${PRIV_IF}" | sed -n 's/^[[:space:]]*\(inet .*\)/  \1/p'
echo "完了。相手ノードと ping が通るか確認してください: ping -c3 <相手のローカルIP>"
