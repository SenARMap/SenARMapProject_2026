# IKU NAVI - 専修大学 生田キャンパス ARナビゲーション

2026年度 専修大学 ネットワーク情報学部 生亀プロジェクト

## 概要

専修大学 生田キャンパス内をナビゲートする AR 対応ナビゲーション Web アプリ。  
CSV ベースのノード・エッジデータから Dijkstra 法で最短経路を計算し、屋外は Google Maps、屋内は SVG フロアマップでルートを表示する。  
AR 領域にはエッジ間の経路写真（Cloudflare R2 CDN 配信）を表示し、スマートフォンの GPS と組み合わせてステップナビゲーションを行う。

## 実際のサイト

本番環境のIKU NAVIへは下のリンクから
[IKU NAVI](https://iku-navi.net/ "IKU NAVI")

![プロジェクトロゴ](/images/logo.png)

## 技術スタック

- **バックエンド:** Python 3 / Flask / Gunicorn / NetworkX / pandas
- **フロントエンド:** HTML / CSS / Vanilla JavaScript / Google Maps API / Inline SVG
- **インフラ:** Docker (Swarm) / ConoHa VPS / Cloudflare Pages（静的配信）
- **ネットワーク:** Cloudflare Tunnels（API 公開）/ Cloudflare R2（画像 CDN）

## ディレクトリ構成

```
SenARMapProject_2026/
├── programs/
│   ├── Website/        # プロジェクト紹介 Web ページ（IKU NAVI）
│   ├── 3D_Graph/       # Flask バックエンド + 3D 経路ビューア (app.py)
│   ├── html/           # ナビゲーション UI (navi/index.html 等)
│   ├── SVG_Pointer/    # SVG 矢印合成ツール
│   ├── Human_Remover/  # 人物モザイク処理ツール
│   └── Image_Renamer/  # 画像リネームツール
├── data/               # CSV / JSON データ（ノード・エッジ・食堂・画像マッピング等）
├── docs/               # 設計ドキュメント
├── deploy_env/         # 本番環境 Docker 構成
└── enviroments/        # 開発環境構成
```


