# Cloudflare Pages 移行計画・手順書

ブラウザに表示される静的コンテンツ（`programs/html`）だけを Cloudflare Pages に移管する。
API・3Dビューア・Counter・監視基盤・Nginx を含むサーバー側の構成は**一切変更せず**、`api.iku-navi.net` サブドメイン経由でそのまま使い続ける。

> 本書内のドメイン名は `iku-navi.net` を前提に記載している。実際のドメインに合わせて読み替えること。

---

## 1. 現状構成と移行後構成

### 現状（Nginx が入口）

```
ユーザー → Cloudflare → cloudflared tunnel → nginx:80
                                              ├─ /          → 静的ファイル (programs/html)
                                              ├─ /api/      → python:8000 (Flask API)
                                              ├─ /3d/       → python:8000 (3Dビューア)
                                              └─ /redirect/ → counter:3000
```

### 移行後（表示は Pages、それ以外はサブドメインで従来どおり）

```
ユーザー ─┬→ iku-navi.net      (Cloudflare Pages) … 静的配信のみ
          │     └ /redirect/* は Redirect Rule で api.iku-navi.net へ 301（QRコード互換用）
          │
          └→ api.iku-navi.net  → cloudflared tunnel → nginx:80（構成そのまま）
                                                       ├─ /api/      → python:8000
                                                       ├─ /3d/       → python:8000
                                                       └─ /redirect/ → counter:3000

サーバー（Docker Swarm）: python / counter / db / nginx / prometheus / grafana / cadvisor / cloudflared
→ スタック構成は変更なし。nginx の静的配信の役割が実質的に不要になるだけ。
```

**必要な変更は次の4点だけ:**

| # | 変更 | 場所 |
|---|------|------|
| 1 | `API_BASE` を `https://api.iku-navi.net` に変更 | フロント3ファイル |
| 2 | `/api/` に CORS ヘッダを追加 | `deploy_env/nginx/nginx.conf` |
| 3 | `config.js` を Pages ビルド時に生成 | Pages のビルド設定 |
| 4 | DNS: メインドメインを Pages へ、`api` サブドメインをトンネルへ | Cloudflare ダッシュボード |

---

## 2. 移行対象の整理

| コンテンツ | 移行先 | 備考 |
|---|---|---|
| `programs/html/index.html`, `style.css`, `images/`, `sitemap.xml` | Pages | そのまま |
| `programs/html/navi/`（ナビUI・AR） | Pages | `API_BASE` の変更のみ |
| `programs/html/blog/` | Pages | HTMLはビルド済みコミットなのでそのまま |
| `programs/html/svg/` | Pages | ナビが相対パス `/svg/...` で取得 → 同一オリジンのままなので変更不要 |
| `navi/script/config.js` | Pages ビルド時に生成 | 現在は nginx entrypoint が生成 |
| `/api/`（Flask API） | **サーバーに残す** | `api.iku-navi.net/api/...` |
| `/3d/`（3Dビューア） | **サーバーに残す** | `api.iku-navi.net/3d/`。ブラウザ遷移なので CORS 不要 |
| `/redirect/`（Counter） | **サーバーに残す** | `api.iku-navi.net/redirect/...`。旧URLは Redirect Rule で救済 |
| カスタムエラーページ | Pages の `404.html` ＋ 従来の nginx エラーページ | 静的側は Pages、API側は従来どおり nginx が返す |

### CORS が必要なのは `/api/` だけ

- `/api/`: Pages 上のページ（`https://iku-navi.net`）から `fetch()` されるクロスオリジン通信 → **CORS 必須**
- `/3d/`, `/redirect/`: ブラウザのページ遷移（トップレベルナビゲーション）→ CORS 不要
- API への `fetch` は GET のみ・カスタムヘッダなしの「単純リクエスト」なので、プリフライト（OPTIONS）対応も不要。`Access-Control-Allow-Origin` を返すだけでよい。

---

## 3. リポジトリ側の変更

### 3.1 フロントエンドの `API_BASE` 変更（3ファイル）

| ファイル | 行（目安） |
|---|---|
| `programs/html/navi/index.html` | `const API_BASE = "";` |
| `programs/html/navi/ar.html` | `const API_BASE = "";` |
| `programs/html/navi/ar-outdoor.html` | `const API_BASE = "";` |

```js
const API_BASE = "https://api.iku-navi.net";
```

※ ローカル開発（nginx 同居構成）では従来どおり空文字が必要になる。切替頻度が高いなら
`const API_BASE = location.hostname === "localhost" ? "" : "https://api.iku-navi.net";`
のようにしておくとローカルと本番を両立できる。

### 3.2 nginx.conf に CORS ヘッダ追加

`deploy_env/nginx/nginx.conf` の `http` ブロックに許可オリジンの map を追加し、`/api/` に `add_header` を入れる:

```nginx
http {
    # 許可するオリジン（本番ドメイン + Pages プレビュー）だけを返す
    map $http_origin $cors_origin {
        default                                   "";
        "https://iku-navi.net"                    $http_origin;
        "https://www.iku-navi.net"                $http_origin;
        "~^https://[a-z0-9-]+\.iku-navi-pages\.pages\.dev$"  $http_origin;
    }

    server {
        # ...既存設定...

        location /api/ {
            add_header Access-Control-Allow-Origin $cors_origin always;
            proxy_pass         http://python:8000/api/;
            # ...既存の proxy_set_header はそのまま...
        }
    }
}
```

※ `pages.dev` の正規表現はプロジェクト名（`iku-navi-pages` の部分）を実際の Pages プロジェクト名に合わせる。
※ Flask 側の変更は不要。

### 3.3 Pages 用の追加ファイル

```
programs/html/
├── _headers     ← 追加（キャッシュ制御）
└── 404.html     ← 追加（deploy_env/nginx/errors/404.html を流用）
```

`programs/html/_headers`:

```
/svg/*
  Cache-Control: public, max-age=86400

/images/*
  Cache-Control: public, max-age=86400

/navi/script/config.js
  Cache-Control: no-cache
```

---

## 4. Cloudflare 側の設定

### 4.1 Pages プロジェクト作成

Workers & Pages → Create → Pages → Connect to Git でリポジトリを選択し、以下を設定:

- **Production branch:** `main`
- **Build command**（config.js の生成。現在の nginx entrypoint の処理を移植）:
  ```bash
  mkdir -p programs/html/navi/script && printf 'const CONFIG = {\n  GOOGLE_MAPS_API_KEY: "%s"\n};\n' "$GOOGLE_MAPS_API_KEY" > programs/html/navi/script/config.js
  ```
- **Build output directory:** `programs/html`
- **環境変数（Production / Preview 両方）:** `GOOGLE_MAPS_API_KEY` = （実キー）

### 4.2 トンネルに api サブドメインを追加

Zero Trust → Tunnels → 対象トンネル → Public Hostname に追加:

| Public Hostname | Service |
|---|---|
| `api.iku-navi.net` | `http://nginx:80` |

既存のメインドメイン向けエントリ（`iku-navi.net` → `nginx:80`）は**切替完了まで残す**（ロールバック保険）。

### 4.3 QRコード等の旧 `/redirect/` URL の救済

配布済みQRコードが `https://iku-navi.net/redirect/...` を指している場合、メインドメインが Pages になると 404 になる。ゾーンの Redirect Rule で転送する:

- Rules → Redirect Rules → Create rule
- **When:** Hostname equals `iku-navi.net` AND URI Path starts with `/redirect/`
- **Then:** Dynamic redirect, 301,
  `concat("https://api.iku-navi.net", http.request.uri.path)`
  （クエリ文字列保持を ON にする）

※ Counter 側は最終的に `api.iku-navi.net` の URL でカウントするため、Counter のリンク定義・集計に影響がないか事前に確認すること。今後印刷するQRコードは最初から `https://api.iku-navi.net/redirect/...` を使う。

### 4.4 Google Maps API キーの制限更新

Google Cloud Console → 認証情報 → 対象キーの「HTTP リファラー制限」に以下を追加:

- `https://iku-navi.net/*`（既存確認）
- `https://*.pages.dev/*`（プレビュー確認用。検証が終わったら外してよい）

---

## 5. 切替手順（本番作業）

作業前に Discord で作業宣言をすること（本番サーバー運用ルール）。

### Phase 1: サーバー側の準備（本番影響なし〜軽微）

1. §3.1〜3.3 の変更をブランチで作成し、レビュー後 `main` にマージ（CI が nginx イメージを再ビルド）。
2. `docker service update`（または stack deploy）で nginx を更新し、CORS ヘッダを確認:
   ```bash
   curl -s -o /dev/null -D - -H "Origin: https://iku-navi.net" https://iku-navi.net/api/all | grep -i access-control
   ```
3. §4.2 のトンネル設定で `api.iku-navi.net` を追加し、`https://api.iku-navi.net/api/all` が JSON を返すことを確認。
   ※ この時点ではメインドメインはまだ nginx 配信のまま。`API_BASE` 変更済みのフロントも `api.iku-navi.net` に向くため、**この Phase の完了時点で新旧どちらの経路でも動く**状態になる。

### Phase 2: Pages 検証（本番影響なし）

4. §4.1 の Pages プロジェクトを作成しデプロイ。
5. `https://<project>.pages.dev` で確認:
   - [ ] トップページ・ブログ・navi UI が表示される
   - [ ] `/navi/script/config.js` にキーが入っている（Google Maps が表示される）
   - [ ] 教室検索 → ルート表示（`api.iku-navi.net/api/` への CORS 通信成功）
   - [ ] AR ページ（ar.html / ar-outdoor.html）で API 取得成功
   - [ ] `/svg/10_1F.svg` が返る・存在しないパスで 404.html が出る

### Phase 3: 本番ドメイン切替

6. Pages プロジェクト → Custom domains → `iku-navi.net`（`www` を使っていればそれも）を追加。
7. DNS のメインドメインレコード（tunnel 向き CNAME）を Pages 向けに変更。**旧レコードの値を必ず控える。**
8. §4.3 の Redirect Rule を作成。
9. 本番ドメインで Phase 2 のチェックリスト＋以下を再実施:
   - [ ] `https://iku-navi.net/redirect/<既存パス>` が 301 → counter の 302 → 遷移先、と流れてカウントされる
   - [ ] `https://api.iku-navi.net/3d/` で 3D ビューアが表示される
10. 数日〜2週間並行監視（Grafana / Cloudflare Analytics でエラー率・Counter 計上を確認）。

### Phase 4: 後片付け（安定確認後・任意）

11. cloudflared の Public Hostname から旧メインドメイン向けエントリを削除。
12. nginx から不要になった設定を削減（任意）:
    - `location /` の静的配信（残っていても害はない）
    - `docker-entrypoint.sh` の config.js 生成と compose の `GOOGLE_MAPS_API_KEY`（Pages 側に移管済み）
13. README / docs の構成図を更新。

---

## 6. ロールバック手順

Phase 4 実施前なら数分で戻せる:

1. DNS のメインドメインを控えておいた旧 CNAME（tunnel 向き）に戻し、Pages の Custom domain を解除。
2. Redirect Rule を無効化。
3. nginx は静的配信を続けているので、それだけで旧構成に復帰する。
   （フロントの `API_BASE` は `api.iku-navi.net` を向いたままだが、Phase 1 でこの経路は生きているため問題なく動く。）

**Phase 4（旧経路の削除）はこの安さのロールバックを捨てる操作**なので、最低 1〜2 週間の安定稼働を確認してから実施すること。

---

## 7. 将来の検討事項

- **nginx の完全撤去**: 本移行では nginx を残すが、将来は cloudflared の Public Hostname のパスルーティング（`api.iku-navi.net/redirect/*` → `counter:3000`、それ以外 → `python:8000`）で nginx なしにでき、2GB VPS のメモリが浮く。その場合 CORS ヘッダは Flask 側（`after_request`）へ移す必要がある。
- **`/api/graph` の CDN キャッシュ**: レスポンス内容はデータ更新まで不変なので、Flask で `Cache-Control` を返して Cloudflare にキャッシュさせるとイベント時のオリジン負荷をさらに下げられる（サーバー側のメモリキャッシュは実装済み）。
- **`/3d/` の保護**: 3D ビューアは開発・検証ツールの色が濃い。一般公開が不要なら Cloudflare Access で `api.iku-navi.net/3d/` を保護できる。
- **ローカル開発**: `wrangler pages dev programs/html` を使うと `_headers` / 404 込みで Pages の挙動をローカル再現できる。
