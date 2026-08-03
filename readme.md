# ids-steam

Steamユーザーレビューデータセットから日本語レビューを抽出・解析するスクリプト群。

## 概要

Mendeley DataのSteamデータセット（games.jsonおよびsteam_data.zip）を自動取得し、高精度な判定ロジックを用いて日本語レビューを抽出・集約します。また、Hugging Faceの感情分析モデルを用いて6つの基本感情軸（喜び・怒り・嫌悪・悲しみ・恐怖・驚き）での感情分析を実施可能です。

- 言語: Python 3
- パッケージマネージャー: uv
- データ出典: <https://data.mendeley.com/datasets/jxy85cr3th/2>

## 構造

```text
ids-steam
├── data/
│   ├── games.json                      - ゲームメタデータ（23,107件）
│   ├── steam_data/                     - 解凍後の全レビューCSV
│   ├── japanese_steam_reviews.csv      - 抽出後の日本語レビューCSV
│   └── japanese_steam_reviews_emotion_sample.csv - 感情分析結果CSV
├── analyze_emotions.py                 - 実際のデータから10件抽出して6感情分析・割合/ランキング算出
├── data_processor.py                   - 日本語判定・CSV/JSON処理の共有モジュール
├── download_data.py                    - データ自動取得・解凍スクリプト
├── main.py                             - 日本語レビュー抽出のメイン実行処理
└── readme.md
```

## 実行方法

| コマンド | 実行内容 |
| --- | --- |
| `uv run download_data.py` | Mendeleyからデータのダウンロードおよび解凍を実行（初回のみ） |
| `uv run main.py` | メイン処理を実行し、日本語レビューを抽出して保存 |
| `uv run analyze_emotions.py` | `japanese_steam_reviews.csv` からランダム10件抽出し、6感情スコア・割合・ランキングを出力 |

## データ構造

### 処理結果ファイル

| ファイル名 | 説明 |
| --- | --- |
| `data/japanese_steam_reviews.csv` | 高精度フィルター（※注1）により抽出された日本語レビューデータ |
| `data/japanese_steam_reviews_emotion_sample.csv` | 6感情のスコア・感情割合(%)・ランキング（上位3感情）を追加した結果ファイル |

### games.jsonのデータと構造

#### 概要と全体構造

games.jsonは、2020年1月から2024年12月までにSteamでリリースされた23,107タイトルのメタデータを格納したJSON形式のファイルです。アプリケーション固有の識別子であるAppIDをキーとして、各ゲームの属性情報が構造化されています。

#### 含まれる主要なデータ項目

ゲームのメタデータは、主に基本情報とシステム情報の2つの側面に分類されて格納されています。

- **ゲームの基本情報と価格情報**
- アプリIDおよびゲームの正式タイトル
- リリース日
- 通常価格や割引に関する情報

- **ゲームの属性とシステム情報**
- アクションやシミュレーションなどのジャンル分類
- マルチプレイヤーやシングルプレイヤーなどのカテゴリ分類
- 対応言語や音声サポートの有無
- 年齢制限のレーティング

---

### steam_data.zipのデータと構造

#### 概要と全体構造

steam_data.zipは、games.jsonに記録されているゲームに対応する3,100万件以上のユーザーレビューを格納した圧縮ファイルです。統計的な偏りを避けるため、レビュー総数が25件未満のゲームは収集対象から除外されています。

解凍すると、Game Reviewsというフォルダの中に、ゲームごとの個別CSVファイルが大量に格納されています。各CSVファイルの名称は、アプリIDとレビュー件数をアンダースコアで組み合わせた形式

#### CSVファイル内に含まれる主要なデータ項目

user, playtime, post_date, helpfulness, review, recommend, early_access_review, appid, game_title, genres, source_file

---

ゲームの性質を表すメタデータと、ユーザーの反応を表すレビューデータが、アプリIDを媒介にして結びつけられるリレーショナル構造になっています。

- 注1

    ```python
    [\u3040-\u309F\u30A0-\u30FF].*[\u3040-\u309F\u30A0-\u30FF].*[\u3040-\u309F\u30A0-\u30FF]
    ```
