import argparse
import os
import random
import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoTokenizer, AutoModelForSequenceClassification

# エクマンの基本6感情
EKMAN_EMOTIONS = ["joy", "sadness", "anger", "fear", "surprise", "disgust"]

# WRIME感情ラベルの日本語マッピング
EMOTION_LABELS_JP = {
    "joy": "喜び",
    "sadness": "悲しみ",
    "anger": "怒り",
    "fear": "恐怖",
    "surprise": "驚き",
    "disgust": "嫌悪",
    "anticipation": "期待",
    "trust": "信頼"
}

MAIN_EMOTIONS_JP = [EMOTION_LABELS_JP[e] for e in EKMAN_EMOTIONS]


class EmotionAnalyzer:
    def __init__(self, model_name: str = "neuralnaut/deberta-wrime-emotions"):
        """
        WRIMEデータセット等でファインチューニングされたモデルを初期化
        """
        print(f"感情分析モデル ({model_name}) を読み込んでいます……")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(self.device)
        self.model.eval()

        self.id2label = self.model.config.id2label

    def analyze_dataframe(self, df: pd.DataFrame, text_column: str = "review", batch_size: int = 32) -> pd.DataFrame:
        """
        データフレーム全体のレビューからバッチ処理で6つの感情スコア・割合(%)・ランキングを高速計算
        """
        df_result = df.copy()
        total_items = len(df_result)
        print(f"合計 {total_items} 件のレビューに対して感情分析を開始します (Device: {self.device}, Batch Size: {batch_size})……")

        texts = df_result[text_column].fillna("").astype(str).tolist()
        emotion_records = []

        # tqdmによる進捗率(%)付きリアルタイムプログレスバー
        with tqdm(total=total_items, desc="感情分析進捗", unit="件") as pbar:
            for i in range(0, total_items, batch_size):
                batch_texts = texts[i : i + batch_size]

                inputs = self.tokenizer(
                    batch_texts,
                    return_tensors="pt",
                    truncation=True,
                    padding=True,
                    max_length=512
                ).to(self.device)

                with torch.no_grad():
                    outputs = self.model(**inputs)
                    logits = outputs.logits
                    scores_batch = torch.sigmoid(logits).cpu().numpy()

                for scores in scores_batch:
                    record = {}
                    for idx, score in enumerate(scores):
                        raw_label = self.id2label.get(idx, f"label_{idx}").lower()
                        jp_label = EMOTION_LABELS_JP.get(raw_label, raw_label)
                        record[jp_label] = float(score)
                    emotion_records.append(record)

                pbar.update(len(batch_texts))

        scores_df = pd.DataFrame(emotion_records)

        # 6つの主要感情の絶対スコアを記録
        for emotion in MAIN_EMOTIONS_JP:
            if emotion in scores_df.columns:
                df_result[f"score_{emotion}"] = scores_df[emotion].round(4)

        # 各行における6感情の相対割合(%)を算出
        six_scores = df_result[[f"score_{e}" for e in MAIN_EMOTIONS_JP]]
        row_sums = six_scores.sum(axis=1).replace(0, 1.0)

        for emotion in MAIN_EMOTIONS_JP:
            df_result[f"ratio_{emotion}_pct"] = ((df_result[f"score_{emotion}"] / row_sums) * 100).round(1)

        # 1位の主要感情および上位3つのランキング表現を追加
        df_result["primary_emotion"] = six_scores.idxmax(axis=1).str.replace("score_", "")

        def get_top_ranking(row):
            ranked = row.sort_values(ascending=False)
            return " > ".join([f"{idx.replace('score_', '')}({val:.2f})" for idx, val in ranked.iloc[:3].items()])

        df_result["emotion_ranking"] = six_scores.apply(get_top_ranking, axis=1)

        return df_result


def main():
    parser = argparse.ArgumentParser(description="Steam日本語レビュー 6感情分析スクリプト")
    parser.add_argument("sample_size", type=int, nargs="?", default=None, help="分析件数 (未指定の場合は全件分析)")
    parser.add_argument("--batch-size", type=int, default=32, help="推論バッチサイズ (デフォルト: 32)")
    args = parser.parse_args()

    input_csv = "data/japanese_steam_reviews.csv"

    if not os.path.exists(input_csv):
        print(f"エラー: 入力ファイル '{input_csv}' が存在しません。先に main.py を実行してください。")
        return

    print(f"'{input_csv}' からデータを読み込んでいます……")
    df_raw = pd.read_csv(input_csv)

    if df_raw.empty or "review" not in df_raw.columns:
        print("エラー: レビューデータが空であるか、'review' 列が存在しません。")
        return

    total_count = len(df_raw)

    if args.sample_size is not None and args.sample_size > 0:
        actual_sample_size = min(args.sample_size, total_count)
        df_target = df_raw.sample(n=actual_sample_size, random_state=42).reset_index(drop=True)
        output_csv = "data/japanese_steam_reviews_emotion_sample.csv"
        print(f"全 {total_count} 件中、指定された {actual_sample_size} 件をランダム抽出して分析します。")
    else:
        df_target = df_raw.reset_index(drop=True)
        actual_sample_size = total_count
        output_csv = "data/japanese_steam_reviews_emotions.csv"
        print(f"全件分析を開始します (合計 {total_count} 件)。")

    analyzer = EmotionAnalyzer()
    df_analyzed = analyzer.analyze_dataframe(df_target, text_column="review", batch_size=args.batch_size)

    # 結果をCSV保存
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_analyzed.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n分析結果をCSVとして保存しました: {output_csv}")

    # シェルへの簡略サマリー表示
    display_limit = min(5 if actual_sample_size > 10 else actual_sample_size, actual_sample_size)
    print("\n" + "=" * 80)
    print(f"【感情分析結果サマリー (全{actual_sample_size}件中 上位{display_limit}件を表示)】")
    print("=" * 80)

    for idx in range(display_limit):
        row = df_analyzed.iloc[idx]
        game_title = row.get("game_title", row.get("appid", "Unknown Game"))
        review_text = str(row["review"]).replace("\n", " ")
        short_text = (review_text[:60] + "...") if len(review_text) > 60 else review_text

        print(f"\n[{idx + 1}/{display_limit}] ゲーム: {game_title}")
        print(f"  レビュー: \"{short_text}\"")
        print(f"  主要感情: 【{row['primary_emotion']}】")
        print(f"  感情ランキング: {row['emotion_ranking']}")

        ratios = [f"{e}:{row[f'ratio_{e}_pct']}%" for e in MAIN_EMOTIONS_JP]
        print(f"  感情割合(%): " + " | ".join(ratios))

    print("\n" + "=" * 80)
    print(f"詳細なCSVデータ出力先: '{output_csv}'")


if __name__ == "__main__":
    main()
