#!/bin/bash
# masterノードで実行する
# 新しいworkerノードに渡すjoinコマンドを生成する
set -e

echo "==> 新しいworkerノード用のjoinコマンドを生成します..."
echo ""
echo "【新しいVPSで以下を順番に実行してください】"
echo ""
echo "# 1. ノードのセットアップ（所要時間: 約3分）"
echo "bash setup-node.sh"
echo ""
echo "# 2. クラスターに参加"
kubeadm token create --print-join-command --ttl 1h
echo ""
echo "# 3. 参加を確認（masterで実行）"
echo "kubectl get nodes"
