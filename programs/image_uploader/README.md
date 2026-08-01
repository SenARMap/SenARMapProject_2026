# 画像一括アップローダー (image_uploader)

Cloudflare Pages + R2 を使った、特定メンバー専用の大量一括画像アップロードツール。
数百〜数千枚の画像を選択し、ブラウザから直接 R2 へ Presigned URL 経由でアップロードする。

- **バックエンド**: Cloudflare Pages Functions（Hono）— `/api/upload-urls` が Presigned PUT URL を発行するだけで、画像本体はサーバーを経由しない
- **フロントエンド**: Vite + Vanilla TypeScript — 同時アップロード数を5〜10件に制限したキュー処理 + 進捗表示
- **認証**: アプリ内ログインなし。**Cloudflare Zero Trust Access** でこのPagesプロジェクト全体を保護する（下記手順3）

---

## 1. ローカル開発

```bash
cd programs/image_uploader
npm install

# ターミナル1: フロントエンドをビルド&監視
npm run dev:vite

# ターミナル2: Pages Functions + 静的配信をローカルで動かす
npm run dev
```

`npm run dev` は `wrangler pages dev dist` を実行し、`http://localhost:8788` で
静的ファイル（`dist/`）と `functions/` 配下のAPIの両方を配信する。

R2への実アップロードをローカルで試す場合は、`programs/image_uploader/.dev.vars` を作成して
以下を設定する（`.gitignore` 済みなのでコミットされない）。

```
R2_ACCOUNT_ID=0d5559e76d5c94e9b66352830d2b86b2
R2_BUCKET_NAME=iku-navi-image
R2_ACCESS_KEY_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
R2_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
```

型チェックのみ行いたい場合: `npm run typecheck`

---

## 2. Cloudflare側の初期設定（初回のみ）

### 2-1. R2バケットを作成

Cloudflareダッシュボード → R2 → バケット作成。実運用では `iku-navi-image` というバケット名で作成済み
（`wrangler.toml` の `bucket_name` / `[vars].R2_BUCKET_NAME` も合わせて設定済み）。

### 2-2. R2 APIトークン（S3互換認証情報）を発行

Presigned URLの署名生成には、R2バインディングではなく **S3互換APIの認証情報** が必要
（署名はネットワーク通信を伴わない純粋な計算なので、Workerからそのまま生成できる）。

1. R2 → 「R2 APIトークンを管理」→ 「APIトークンを作成」
2. 権限: 対象バケットへの「オブジェクト読み取り・書き込み」のみ（アカウント全体の権限は不要）
3. 発行された **Access Key ID** / **Secret Access Key** / **アカウントID** を控える

### 2-3. R2の認証情報をひかえておく

発行した Access Key ID / Secret Access Key / アカウントID は、4-1 でPagesプロジェクトを
作成する際にダッシュボードの環境変数／シークレットとして設定する（このリポジトリには書かない）。

`wrangler.toml` の `[vars]` にある `R2_ACCOUNT_ID` / `R2_BUCKET_NAME` は秘密情報ではないので
平文のままでよいが、実際の値に書き換えておくこと。

### 2-4. R2バケットにCORSを設定（必須）

ブラウザは Pages のドメインから `https://<accountid>.r2.cloudflarestorage.com` へ直接PUTするため、
R2バケット側でCORSを許可しないとブラウザにブロックされる。

`r2-cors.json` の `AllowedOrigins` を実際のPagesドメイン（下記手順4で決まるURL）に書き換えてから:

```bash
npx wrangler r2 bucket cors set iku-navi-image --rules r2-cors.json
```

ダッシュボードから設定する場合は R2 → 対象バケット → 設定 → CORSポリシー でも同じ内容を登録できる。

---

## 3. Zero Trust Access でのアクセス制限

このアプリ自体にはログイン機能を実装していない。アクセス制御は Cloudflare Zero Trust 側で行う。

**現在の実運用設定（IDP: GitHub）:**

- アプリケーション名: 画像一括アップローダー
- 保護する宛先: `image-upload.iku-navi.net`
- IDP: GitHub
- ポリシー `GitHubAuth`: Allow / Include = GitHub Organization が `SenARMapOrg`

> 当初の要望は「`@senshu-u.jp` のGoogleアカウントのみ許可」だったが、大学アカウント縛りではなく
> 開発チーム（GitHub Org `SenARMapOrg` 所属者）縛りに変更する方針で確定。
> 将来Googleアカウント制限に戻したくなった場合は以下の手順で設定し直せる。

**（参考）Googleアカウント（`@senshu-u.jp`）制限にする場合:**

1. Cloudflare One（Zero Trust）ダッシュボード → **Settings → Authentication** で
   ログインメソッドに **Google**（Google Workspaceの場合は「Google Workspace」タイプ）を追加する
2. **Access → Applications** → 対象アプリケーションの **Policies** で
   Include: `Emails ending in` → `@senshu-u.jp` のルールに変更する
   （もしくは Login Methods を Google に限定した上で `Email domain` ルールを併用するとより厳密）

---

## 4. デプロイ（Git連携 — 本体サイトと同じ方式）

本体サイト（`programs/html`）と同様、**Cloudflareダッシュボードでこのリポジトリと連携し、
`main`にマージされるたびに自動ビルド・自動デプロイ**する方式にする（`wrangler pages deploy`による
手動デプロイは行わない。詳細は `docs/cloudflare_pages_migration.md` の本体サイト移行手順を参照）。

### 4-1. 初回セットアップ（ダッシュボードでの作業）

Cloudflareダッシュボード → **Workers & Pages → Create → Pages → Connect to Git** で
このリポジトリを選択し、以下を設定する（**モノレポなので Root directory の指定が必須**）。

| 設定項目 | 値 |
|---|---|
| Production branch | `main` |
| Root directory (Advanced) | `programs/image_uploader` |
| Build command | `npm install && npm run build` |
| Build output directory | `dist` |
| 環境変数（Production / Preview 両方） | `R2_ACCOUNT_ID`, `R2_BUCKET_NAME` |
| シークレット（Production / Preview 両方） | `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY` |

Root directory を `programs/image_uploader` に設定すると、Cloudflareはそのディレクトリ内の
`functions/` を自動検出してPages Functionsとしてデプロイする（`wrangler.toml` の
`pages_build_output_dir` はローカルの `wrangler pages dev`/`deploy` 用で、ダッシュボードのGit連携ビルドには使われない）。

環境変数・シークレットはダッシュボードの Pages プロジェクト → Settings → Environment variables から設定する
（2-2で発行したR2 APIトークンの値をここに入れる。`wrangler pages secret put` によるCLI設定でも同じ場所に反映される）。

### 4-2. 初回デプロイ後にやること

**実運用の設定値（確定済み）:**

- Pagesプロジェクト名: `senarmapproject-2026-image-uploader`
- カスタムドメイン: `image-upload.iku-navi.net`（`*.pages.dev` のデフォルトURLでもアクセス可能）

カスタムドメインは **Pagesプロジェクト → Custom domains → Add a custom domain** から追加する。
ここから追加すると、正しい種類・プロキシ設定のDNSレコードがCloudflare側で自動生成される
（DNSレコードタブから手動でCNAME/Aレコードを作らないこと。手動で作ると設定ミスの元）。

### 4-2-1. トラブルシューティング: カスタムドメインで 522 (Connection timed out) になる場合

Pagesはサーバーレスなのでオリジンサーバーがダウンして522になることは基本的にない。
ほぼ確実に **DNS側の設定ミス** が原因。Cloudflareダッシュボード → `iku-navi.net` → DNS → レコード で
`image-upload` の行を確認する。

- **原因1（よくある）**: `A`レコードなど、Pages以外を指す古いレコードが残っている（例: 旧VPSのIP）。
  → 削除する。
- **原因2**: レコードは `CNAME` → `senarmapproject-2026-image-uploader.pages.dev` で正しいが、
  プロキシ状態が **「DNSのみ」(グレークラウド)** になっている。Pagesのカスタムドメインは
  **「プロキシ済み」(オレンジクラウド)** である必要がある。
- 上記どちらであっても、DNSレコードを直接編集するより、一度そのレコードを削除してから
  4-2 の「Custom domains → Add a custom domain」でやり直すのが一番確実
  （Cloudflareが正しいCNAME + プロキシ状態を自動生成するため）。

### 4-3. 以降の更新

`main` にマージするだけで自動的に再ビルド・再デプロイされる。サーバー作業・手動デプロイは不要。
PRごとにプレビューURL（`*.pages.dev`）も自動発行される。

手元で最終確認だけしたい場合は `npm run build && npx wrangler pages deploy dist` で
手動デプロイすることも可能だが、通常運用では使わない。

---

## 5. 使い方（利用者向け）

1. Zero Trust の認証画面で許可されたアカウント（現状: `SenARMapOrg` のGitHubアカウント）でログイン
2. 「ここをクリックして画像を選択」から数百〜数千枚をまとめて選択
3. 同時アップロード数（デフォルト6）を必要に応じて変更し、「アップロード開始」を押す
4. 進捗バーと「◯◯ / ◯◯ 件完了」が表示される。失敗したファイルがあれば一覧に表示される
5. アップロードされた画像は R2 バケットの**ルート直下**に**元のファイル名のまま**保存される
   （同名ファイルは上書きされる）

---

## 実装メモ

- `functions/api/[[route]].ts`: Honoアプリ本体。`POST /api/upload-urls` が
  `{ filenames: string[] }` を受け取り `@aws-sdk/client-s3` + `@aws-sdk/s3-request-presigner` で
  15分有効のPresigned PUT URLを配列生成して返す（1リクエストあたり最大2000件、超える場合はフロント側で分割送信）。
  ファイル名はパストラバーサル対策のsanitizeのみ行い、バケットルート直下にそのままのファイル名で
  保存する（同名ファイルは意図的に上書きされる。重複排除やuuid付与はしていない）。
- `src/main.ts`: `runWithConcurrencyLimit()` で同時実行数を制限したキュー処理を素朴に実装
  （`p-limit` 等の外部ライブラリは使わず、この用途には数十行の自前実装で十分なため依存を増やしていない）。
- Presigned URL 発行時に `ContentType` を署名対象に含めていないため、PUT時にどんな `Content-Type` を
  送っても署名エラーにならない（フロントは `file.type` をそのまま送るのみ）。
