# IKU NAVI - 専修大学 生田キャンパス ARナビゲーション

2026年度 専修大学 生田プロジェクト

## 概要

専修大学 生田キャンパス内をナビゲートするARマップアプリケーション。  
CSVベースのノード・エッジデータから最短経路を計算し、3Dマップで経路を可視化する。  
最終的には屋内が写真に矢印を合成するシンプルなARマップ、外はカメラとGPSを用いたARマップへの発展を目指している。

## 実際のサイト

本番環境のIKU NAVIへは下のリンクから
[IKU NAVI](https://iku-navi.net/ "IKU NAVI")

![プロジェクトロゴ](/images/logo.png)

## 技術スタック

- **バックエンド:** Python / Flask / NetworkX / pandas
- **フロントエンド:** HTML / CSS / JavaScript
- **インフラ:** Docker

## ディレクトリ構成

```
SenARMapProject_2026/
├── programs/
│   ├── Website/        # Webアプリ本体 (Flask)
│   ├── 3D_Graph/       # 3D経路ビューア
│   ├── SVG_Pointer/    # SVG矢印合成ツール
│   ├── Human_Remover/  # 人物モザイク処理ツール
│   ├── Image_Renamer/  # 画像リネームツール
│   └── html/           # 静的HTMLページ
├── data/               # CSVデータ（ノード・エッジ定義）
├── docs/               # 設計ドキュメント
├── deploy_env/         # 本番環境 Docker構成
└── enviroments/        # 開発環境構成
```


