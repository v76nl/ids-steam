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
│   ├── japanese_steam_reviews_emotions.csv - 全件感情分析結果CSV
│   └── japanese_steam_reviews_emotion_sample.csv - サンプル感情分析結果CSV
├── analyze_emotions.py                 - 6感情分析モジュール（全件/件数指定対応・tqdm進捗表示）
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
| `uv run analyze_emotions.py` | `japanese_steam_reviews.csv` の全件に対して6感情分析を実行（プログレスバー表示） |
| `uv run analyze_emotions.py 100` | 指定件数（例: 100件）をランダム抽出し感情分析を実行 |

## データ構造

### 処理結果ファイル

| ファイル名 | 説明 |
| --- | --- |
| `data/japanese_steam_reviews.csv` | 高精度フィルター（※注1）により抽出された日本語レビューデータ |
| `data/japanese_steam_reviews_emotions.csv` | 全件感情分析結果（6感情スコア・割合(%)・ランキング） |
| `data/japanese_steam_reviews_emotion_sample.csv` | 件数指定時の感情分析結果（6感情スコア・割合(%)・ランキング） |

### games.jsonのデータと構造

2020年1月から2024年12月までにSteamでリリースされた23,107タイトルのメタデータ。AppIDをキーとするJSON構造。

- **基本情報**: AppID, タイトル, リリース日, 価格情報
- **属性情報**: ジャンル, カテゴリ, 対応言語, 年齢制限

### steam_data.zipのデータと構造

3,100万件以上のユーザーレビュー（レビュー数25件未満のタイトルは除外）。解凍後は `AppID_レビュー数.csv` の形式で個別格納。

- **CSVデータ項目**: `user`, `playtime`, `post_date`, `helpfulness`, `review`, `recommend`, `early_access_review`, `appid`, `game_title`, `genres`, `source_file`

---

- 注1：日本語判定フィルター（`data_processor.py`）
  - 連続したひらがな2文字以上を含む
  - かな（ひらがな・カタカナ）の総文字数が10文字以上
  - レビュー全体における「かな密度」が 5% 以上
