# Kubernetes デプロイガイド

> **⚠️ このドキュメントは現在の本番構成ではありません。**
>
> Kubernetes は検証用として試みたが、以下の理由から採用を見送り、**Docker Swarm** に切り替えた。
> - 2GB VPS 単台では kubeadm + Calico のオーバーヘッドが大きい
> - ワーカートークンの 24 時間有効期限など運用コストが高い
> - 同等のスケールアウトが Docker Swarm で低コストに実現できる
>
> **現行の本番デプロイ手順は [`swarm.md`](./swarm.md) を参照してください。**
>
> このファイルは k8s 構成の記録として残しています。

---

`deploy_env/k8s/` に配置されたマニフェストを使い、docker-compose 環境と同等の構成を kubeadm クラスタ上で動かすための手順書です。

## 構成概要

```
Cloudflare Tunnel (cloudflared × 2)
        ↓
    nginx (× 2)  ←── static files / リバースプロキシ
    ├── /3d/, /api/     → python (gunicorn × 2)
    └── /redirect/      → counter (Rails × 2)
                               ↓
                          db (MariaDB, StatefulSet × 1)

監視: Prometheus / Grafana / cAdvisor / node-exporter / kube-state-metrics
```

| コンポーネント | イメージ | Port |
|---|---|---|
| nginx | `ghcr.io/senarmaporg/iki_project_2026_nginx:latest` | 80 |
| python | `ghcr.io/senarmaporg/iki_project_2026_python:latest` | 8000 |
| counter | `ghcr.io/senarmaporg/iki_project_2026_counter:latest` | 3000 |
| db | `mariadb:11` | 3306 |
| cloudflared | `cloudflare/cloudflared:latest` | — |
| prometheus | `prom/prometheus:latest` | 9090 |
| grafana | `grafana/grafana:latest` | 3000 |

---

## 前提条件

- Ubuntu 22.04 / 24.04 の VPS が 1 台以上（master 兼用でも可）
- 各 VPS に SSH でログインできること
- Cloudflare Tunnel のトークンが発行済みであること
- GHCR のイメージが push 済みであること

---

## 0. UFW ファイアウォール設定（全ノード共通・最初に実施）

### なぜ最初に設定するか

kubeadm + Calico は Pod ネットワークの転送に iptables を多用します。UFW のデフォルト設定（`DEFAULT_FORWARD_POLICY=DROP`）のままだと Pod 間通信がすべて遮断されます。**ノードセットアップ前に以下を適用してください。**

### Step 1: forward ポリシーを ACCEPT に変更

```bash
# /etc/default/ufw の DEFAULT_FORWARD_POLICY を DROP → ACCEPT に変更
sudo sed -i 's/^DEFAULT_FORWARD_POLICY=.*/DEFAULT_FORWARD_POLICY="ACCEPT"/' /etc/default/ufw
```

### Step 2: UFW ルール設定

```bash
# リセット（既存ルールを削除）
sudo ufw --force reset

# デフォルトポリシー
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw default allow routed        # Pod ネットワークのルーティングを許可

# ループバック（必須）
sudo ufw allow in on lo
sudo ufw allow out on lo

# SSH（先に許可しないとロックアウトされる）
sudo ufw allow 22/tcp

# Kubernetes API サーバー（kubectl・worker ノードが使用）
sudo ufw allow 6443/tcp

# Calico VXLAN（ノード間 Pod ネットワーク通信）
sudo ufw allow 4789/udp

# kubelet API（kubectl logs / exec がノード間で使用）
sudo ufw allow 10250/tcp

# Pod ネットワーク CIDR からのトラフィックを許可
sudo ufw allow from 10.244.0.0/16
sudo ufw allow to   10.244.0.0/16

# UFW を有効化
sudo ufw --force enable
sudo ufw status verbose
```

### worker ノードが存在する場合

プライベートネットワーク（eth1）側からのトラフィックをすべて許可しておくと管理が楽です。

```bash
# プライベートネットワーク CIDR を確認
ip a show eth1

# そのセグメントをすべて許可（例: 10.10.10.0/24）
sudo ufw allow in on eth1
```

### 許可ポート一覧

| ポート | プロトコル | 用途 |
|---|---|---|
| 22 | TCP | SSH |
| 6443 | TCP | Kubernetes API サーバー |
| 4789 | UDP | Calico VXLAN（ノード間 Pod 通信） |
| 10250 | TCP | kubelet API（kubectl exec/logs） |
| 10.244.0.0/16 | — | Pod ネットワーク CIDR 全体 |

> **このプロジェクトで HTTP/HTTPS ポートが不要な理由**  
> 外部からのアクセスはすべて Cloudflare Tunnel（cloudflared）が担当するため、80 番・443 番をパブリックに開放する必要はありません。

---

## 1. ノードのセットアップ（全ノード共通）

master・worker 全台で実行します。

```bash
bash deploy_env/k8s/setup-node.sh
```

このスクリプトは以下を行います。

- swap 無効化（K8s 必須要件）
- カーネルモジュール / iptables 設定
- containerd インストール・設定（SystemdCgroup 有効化）
- kubeadm / kubelet / kubectl インストール（v1.31 固定）

---

## 2. master ノードのセットアップ

master ノード 1 台のみで実行します。

```bash
# eth1 のプライベート IP を確認
ip a | grep "inet " | grep eth1

bash deploy_env/k8s/setup-master.sh <プライベートIP>
# 例: bash deploy_env/k8s/setup-master.sh 10.10.10.208
```

このスクリプトは以下を行います。

1. `kubeadm init` でクラスタ初期化
2. `kubectl` の設定（root・project-prod ユーザー）
3. CNI プラグイン（Calico v3.28）インストール
4. StorageClass（local-path-provisioner v0.30）インストール・デフォルト設定

> **local-path-provisioner について**  
> kubeadm クラスタには StorageClass がデフォルトで存在しないため、PVC（prometheus・grafana のデータ永続化）が Pending のまま起動しません。`setup-master.sh` が自動でインストールします。

完了後、ノードの Ready を確認します（1〜2 分かかります）。

```bash
kubectl get nodes
kubectl get storageclass
```

---

## 3. worker ノードの追加（任意）

worker を追加する場合は、master ノードで以下を実行して join コマンドを生成します。

```bash
bash deploy_env/k8s/add-worker.sh
```

出力された `kubeadm join ...` コマンドを worker ノードで実行します。

```bash
# worker ノードで実行
sudo kubeadm join <master-ip>:6443 --token <token> --discovery-token-ca-cert-hash sha256:<hash>
```

---

## 4. Secrets の準備

`secrets.yaml` は Git 管理対象外です。テンプレートをコピーして値を記入します。

```bash
cd deploy_env/k8s
cp secrets.yaml.template secrets.yaml
```

`secrets.yaml` を編集して各値を入力します（`stringData` なので base64 不要・平文で記載）。

```yaml
stringData:
  DB_ROOT_PASSWORD: "your-root-password"
  DB_NAME: "counters"
  DB_USER: "counters"
  DB_PASSWORD: "your-db-password"
  SECRET_KEY_BASE: "64文字以上のランダム文字列"
  GOOGLE_MAPS_API_KEY: "AIza..."
  GF_SECURITY_ADMIN_USER: "admin"
  GF_SECURITY_ADMIN_PASSWORD: "your-grafana-password"
  TUNNEL_TOKEN: "eyJ..."   # Cloudflare ダッシュボードで発行
```

SECRET_KEY_BASE の生成例：

```bash
openssl rand -hex 64
```

> **注意**: `secrets.yaml` はコミットしないでください。`.gitignore` 済みですが、誤って `git add -A` した場合はすぐに削除してください。

---

## 5. アプリケーションのデプロイ

master ノードで実行します。

```bash
cd deploy_env/k8s
bash deploy.sh
```

スクリプトは以下の順序で適用します。

1. Namespace (`iki-project`) 作成
2. `secrets.yaml` を適用
3. 全マニフェストを `kubectl apply -k .` で適用
4. 各 Deployment / StatefulSet の rollout 完了を待機

---

## 6. 動作確認

```bash
# Pod 一覧
kubectl get pods -n iki-project

# Service 一覧
kubectl get svc -n iki-project

# 問題が起きている Pod のログを確認
kubectl logs -n iki-project <pod-name>

# Pod の詳細（probe 失敗など Events を確認）
kubectl describe pod -n iki-project <pod-name>
```

全 Pod が `Running` かつ `READY` になれば完了です。

```
NAME                              READY   STATUS    RESTARTS
cloudflared-xxx                   1/1     Running   0
counter-xxx                       1/1     Running   0
db-0                              1/1     Running   0
grafana-xxx                       1/1     Running   0
kube-state-metrics-xxx            1/1     Running   0
nginx-xxx                         1/1     Running   0
prometheus-xxx                    1/1     Running   0
python-xxx                        1/1     Running   0
```

---

## 7. 監視サービスへのアクセス

Prometheus と Grafana は ClusterIP のため、`kubectl port-forward` でローカルからアクセスします。

```bash
# Prometheus
kubectl port-forward -n iki-project svc/prometheus 9090:9090

# Grafana
kubectl port-forward -n iki-project svc/grafana 3000:3000
```

ブラウザで `http://localhost:9090`（Prometheus）・`http://localhost:3000`（Grafana）を開きます。  
Grafana の初期ユーザー/パスワードは secrets.yaml の `GF_SECURITY_ADMIN_USER` / `GF_SECURITY_ADMIN_PASSWORD` です。  
Prometheus データソースは起動時に自動プロビジョニングされます。

---

## 8. 更新・再デプロイ

イメージが更新された場合は deploy.sh を再実行するか、手動で rollout restart します。

```bash
# 全アプリを再起動
kubectl rollout restart deployment/python deployment/nginx deployment/counter -n iki-project

# 特定の Deployment だけ
kubectl rollout restart deployment/nginx -n iki-project
```

30 分ごとの自動更新 CronJob（`auto-update`）が python・nginx・counter を定期的に再起動します。

---

## 9. worker ノードの削除

```bash
# master で実行
kubectl drain <node-name> --ignore-daemonsets --delete-emptydir-data
kubectl delete node <node-name>
```

---

## トラブルシューティング

### nginx Pod が Ready にならない

```bash
kubectl describe pod -n iki-project <nginx-pod>
```

`Events` に `Readiness probe failed` が出ている場合、コンテナ起動ログを確認します。

```bash
kubectl logs -n iki-project <nginx-pod>
```

docker-entrypoint.sh のエラー（`mkdir` 失敗など）が原因の場合は GHCR のイメージが正しいか確認してください。

### cloudflared が再起動し続ける

```bash
kubectl logs -n iki-project <cloudflared-pod>
```

`TUNNEL_TOKEN` が正しいか確認します。Cloudflare ダッシュボードでトンネルが Active 状態になっているかも確認してください。

### PVC が Pending のまま

```bash
kubectl get pvc -n iki-project
kubectl get storageclass
```

StorageClass が存在しない場合は `setup-master.sh` が正常に完了していません。手動でインストールします。

```bash
kubectl apply -f https://raw.githubusercontent.com/rancher/local-path-provisioner/v0.0.30/deploy/local-path-storage.yaml
kubectl patch storageclass local-path -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

### counter が CrashLoopBackOff になる

DB の初期化が完了する前に counter が起動しようとしている可能性があります。initContainer が MariaDB のポート 3306 が開くまで待機しますが、DB の初期化（テーブル作成）に時間がかかる場合は自動で retry されます。数分待ってから再確認してください。

```bash
kubectl logs -n iki-project <counter-pod> -c wait-for-db
kubectl logs -n iki-project <counter-pod>
```

### イメージが pull できない（ImagePullBackOff）

GHCR のイメージがプライベートの場合、`imagePullSecrets` の設定が必要です。

```bash
# GHCR 認証情報を Secret として登録
kubectl create secret docker-registry ghcr-secret \
  --docker-server=ghcr.io \
  --docker-username=<GitHubユーザー名> \
  --docker-password=<GitHubトークン> \
  -n iki-project
```

各 Deployment の `spec.template.spec` に以下を追加します。

```yaml
imagePullSecrets:
  - name: ghcr-secret
```

---

## ファイル構成

```
deploy_env/k8s/
├── namespace.yaml                  # Namespace 定義
├── secrets.yaml.template           # Secret テンプレート（コピーして使用）
├── secrets.yaml                    # 実際の Secret（.gitignore 済み・要作成）
├── kustomization.yaml              # kubectl apply -k のエントリポイント
├── setup-node.sh                   # 全ノード共通セットアップ
├── setup-master.sh                 # master セットアップ（Calico + local-path）
├── add-worker.sh                   # worker join コマンド生成
├── deploy.sh                       # アプリデプロイスクリプト
├── app/
│   ├── nginx-deployment.yaml
│   ├── nginx-service.yaml
│   ├── python-deployment.yaml
│   ├── python-service.yaml
│   ├── counter-deployment.yaml
│   ├── counter-service.yaml
│   ├── db-statefulset.yaml
│   ├── db-service.yaml             # Headless Service（StatefulSet 用）
│   └── auto-update-cronjob.yaml    # 30分ごとに python/nginx/counter を再起動
├── tunnel/
│   └── cloudflared-deployment.yaml
└── monitoring/
    ├── prometheus-*.yaml
    ├── grafana-*.yaml
    ├── cadvisor-*.yaml
    ├── node-exporter-*.yaml
    └── kube-state-metrics-*.yaml
```
