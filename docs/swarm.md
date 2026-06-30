# Docker Swarm 運用手順

## 概要

平常時は **2GB VPS（マネージャー）** のみで動作し、イベント時に **4GB サーバー（ワーカー）** を追加する構成。

```
平常時                          イベント時
┌─────────────────────┐         ┌─────────────────────┐
│  Manager (2GB VPS)  │         │  Manager (2GB VPS)  │
│  ・nginx            │         │  ・nginx            │
│  ・db               │   ───→  │  ・db               │
│  ・python ×1        │         │  ・python ×2        │
│  ・counter ×1       │         │  ・counter ×2       │
│  ・grafana          │         │  ・grafana          │
│  ・prometheus       │         │  ・prometheus       │
│  ・cloudflared      │         │  ・cloudflared      │
│  ・cadvisor         │         │  ・cadvisor         │
└─────────────────────┘         └─────────────────────┘
                                ┌─────────────────────┐
                                │  Worker (4GB)       │
                                │  ・python ×2        │
                                │  ・counter ×2       │
                                │  ・cadvisor         │
                                └─────────────────────┘
```

### サービスの配置ルール

| サービス | 配置 | 理由 |
|---|---|---|
| python | 全ノードに分散 | スケール対象 |
| counter | 全ノードに分散 | スケール対象 |
| cadvisor | 全ノード（global） | 各ノードのメトリクス収集 |
| nginx | マネージャー固定 | cloudflared と同居 |
| db | マネージャー固定 | ボリュームデータがある |
| prometheus | マネージャー固定 | docker.sock 参照 + ボリューム |
| grafana | マネージャー固定 | ボリュームデータがある |
| cloudflared | マネージャー固定 | トンネルの入口 |

---

## 前提条件

- マネージャー・ワーカー両方に Docker がインストール済み（`deploy.sh` 実行済み）
- 両サーバー間で以下のポートが開いていること（ファイアウォール設定）:
  - `2377/tcp` — Swarm クラスター管理
  - `7946/tcp,udp` — ノード間通信
  - `4789/udp` — オーバーレイネットワーク (VXLAN)
- GHCR イメージの pull 権限があること（`docker login ghcr.io`）

---

## 初回セットアップ（Swarm 初期化）

### 1. マネージャーノードで Swarm を初期化

```bash
# マネージャー(2GB VPS)で実行
docker swarm init --advertise-addr <MANAGER_の外部IP>
```

成功すると以下のようなトークンが表示される（後で使う）:

```
To add a worker to this swarm, run the following command:
    docker swarm join --token SWMTKN-1-xxxx <MANAGER_IP>:2377
```

### 2. マネージャーの状態確認

```bash
docker node ls
# NAME    STATUS    AVAILABILITY   MANAGER STATUS
# xxx *   Ready     Active         Leader
```

---

## スタックのデプロイ

### 1. リポジトリの取得と .env の配置

```bash
cd /srv
git clone https://github.com/SenARMapOrg/SenARMapProject_2026.git
cd SenARMapProject_2026/deploy_env

# sample.env をコピーして各値を設定
cp sample.env .env
vim .env
```

### 2. GHCR にログイン

```bash
echo <GHCR_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

### 3. スタックをデプロイ

> **重要:** `docker stack deploy` は `.env` を自動で読み込まない。
> `source .env` でシェルに読み込んでから deploy する。
>
> `docker compose config` を間に挟む方法は**使わない**こと。
> Docker Compose v2 が `depends_on` をマップ形式に正規化するため、
> `docker stack deploy` が "must be a list" エラーを出す。

```bash
cd /srv/SenARMapProject_2026/deploy_env

set -a && source .env && set +a
docker stack deploy \
  --with-registry-auth \
  -c docker-compose.yml \
  iku
```

### 4. デプロイ確認

```bash
# サービス一覧と起動状況
docker service ls

# 各サービスのタスク（コンテナ）の配置確認
docker stack ps iku

# ログ確認 (例: python サービス)
docker service logs iku_python -f
```

---

## 状態確認コマンド集

```bash
# ノード一覧
docker node ls

# スタック全体のサービス状況
docker service ls

# タスク（コンテナ）の配置とノード
docker stack ps iku --no-trunc

# 特定サービスの詳細
docker service ps iku_python

# リソース使用状況
docker stats $(docker ps -q)
```

---

## イベント時：ワーカーの増設

### 手順1. トークンを確認（マネージャーで実行）

```bash
docker swarm join-token worker
```

### 手順2. ワーカー（4GB サーバー）の初期設定

4GB サーバーに SSH し、Docker をインストール:

```bash
# 4GB サーバーで実行
bash /path/to/deploy.sh   # または手動で Docker インストール

# GHCR にログイン
echo <GHCR_TOKEN> | docker login ghcr.io -u <GITHUB_USERNAME> --password-stdin
```

### 手順3. ワーカーを Swarm に参加させる（ワーカーで実行）

```bash
# 手順1 で取得したコマンドをそのまま実行
docker swarm join --token SWMTKN-1-xxxx <MANAGER_IP>:2377
```

### 手順4. ノード参加を確認（マネージャーで実行）

```bash
docker node ls
# HOSTNAME    STATUS    AVAILABILITY   MANAGER STATUS
# manager *   Ready     Active         Leader
# worker      Ready     Active
```

cadvisor は `mode: global` のため、ワーカー参加と同時に自動でデプロイされる。

### 手順5. python / counter をスケールアップ

```bash
# イベント規模に応じて調整（例: 各4レプリカ）
docker service scale iku_python=4 iku_counter=4

# 分散状況を確認
docker service ps iku_python
```

> **workers の調整:** 平常時は `gunicorn -w 4` を使っているが、
> スケールアップ後は 4レプリカ × 4workers = 16並列になる。
> さらに増やしたい場合は `docker service update --args "gunicorn -w 8 ..." iku_python`。

---

## イベント終了後：ワーカーの撤去

### 手順1. ワーカーをドレインしてタスクをマネージャーに移す

```bash
# マネージャーで実行
docker node update --availability drain <WORKER_NODE_ID>

# タスクが移動するまで待つ（30秒程度）
watch docker stack ps iku
```

### 手順2. サービスを平常時のレプリカ数に戻す

```bash
docker service scale iku_python=2 iku_counter=2
```

### 手順3. ワーカーを Swarm から離脱させる

```bash
# ワーカーサーバーで実行
docker swarm leave

# マネージャーで「Down」になったノードを削除
docker node rm <WORKER_NODE_ID>
```

### 手順4. ノードが削除されたか確認

```bash
docker node ls
# manager のみが表示されればOK
```

---

## ローリングアップデート（イメージ更新）

コード変更後に CI で新イメージがビルドされたら:

```bash
cd /srv/SenARMapProject_2026/deploy_env
git pull

# compose.yml の変更も含めて再デプロイ（設定変更 + イメージ更新を一括適用）
set -a && source .env && set +a
docker stack deploy \
  --with-registry-auth \
  -c docker-compose.yml \
  iku
```

イメージだけ更新したい場合:

```bash
# 最新イメージを pull してローリングアップデート
docker service update --image ghcr.io/senarmaporg/iki_project_2026_python:latest \
  --with-registry-auth iku_python
```

`update_config.order: start-first` が設定されているため、新コンテナが先に起動してから
旧コンテナが停止する（ゼロダウンタイムアップデート）。

---

## prometheus の設定変更

prometheus.yml を更新した場合、Docker config を更新してサービスを再起動:

```bash
# config の更新は削除→再作成が必要
docker config rm iku_prometheus_config

# スタック再デプロイで config が再作成される
set -a && source .env && set +a
docker stack deploy \
  --with-registry-auth \
  -c docker-compose.yml \
  iku
```

---

## トラブルシューティング

### サービスが起動しない

```bash
# タスクのエラーを確認
docker service ps iku_python --no-trunc

# ログ確認
docker service logs iku_python --tail 50
```

### counter が DB に繋がらない

Swarm では `depends_on` が無視されるため、DB が起動する前に counter が起動してしまう場合がある。
`restart_policy.delay: 15s` と `max_attempts: 5` が設定されているので、通常は自動リトライで回復する。

手動でリトライを促したい場合:

```bash
docker service update --force iku_counter
```

### ワーカーノードが Pending のまま

ファイアウォールのポート（2377/tcp, 7946/tcp+udp, 4789/udp）が開いているか確認:

```bash
# マネージャー側で確認
sudo ufw status
# または
sudo iptables -L -n | grep -E "2377|7946|4789"
```

### cadvisor がワーカーで起動しない

`mode: global` のサービスなのでワーカー参加時に自動起動するはず。
起動していない場合:

```bash
docker service ps iku_cadvisor
docker service logs iku_cadvisor
```

### prometheus が cadvisor を scrape できない

prometheus が docker.sock にアクセスできているか確認:

```bash
# prometheus コンテナ内で確認
docker exec $(docker ps -q -f name=iku_prometheus) \
  wget -qO- http://localhost:9090/api/v1/targets | python3 -m json.tool | grep "job\|health"
```
