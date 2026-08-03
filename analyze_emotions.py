import os
import random
import pandas as pd
import torch
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

    def analyze_text(self, text: str) -> dict:
        """
        単一テキストに対する感情スコア（0.0 ~ 1.0）を試算
        """
        if not text or not isinstance(text, str):
            return {EMOTION_LABELS_JP[e]: 0.0 for e in EKMAN_EMOTIONS}

        inputs = self.tokenizer(text, return_tensors="pt", truncation=True, max_length=512).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            scores = torch.sigmoid(logits[0]).cpu().numpy()

        results = {}
        for idx, score in enumerate(scores):
            raw_label = self.id2label.get(idx, f"label_{idx}").lower()
            jp_label = EMOTION_LABELS_JP.get(raw_label, raw_label)
            results[jp_label] = float(score)

        return results

    def analyze_dataframe(self, df: pd.DataFrame, text_column: str = "review") -> pd.DataFrame:
        """
        データフレーム全体のレビューから6つの感情スコア・割合(%)・ランキングを計算
        """
        df_result = df.copy()
        print(f"合計 {len(df_result)} 件のレビューに対して感情分析を実行中……")

        emotion_records = []
        for text in df_result[text_column]:
            scores = self.analyze_text(text)
            emotion_records.append(scores)

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
    input_csv = "data/japanese_steam_reviews.csv"
    output_csv = "data/japanese_steam_reviews_emotion_sample.csv"
    sample_size = 10

    if not os.path.exists(input_csv):
        print(f"エラー: 入力ファイル '{input_csv}' が存在しません。先に main.py を実行してください。")
        return

    print(f"'{input_csv}' からデータを読み込んでいます……")
    df_raw = pd.read_csv(input_csv)

    if df_raw.empty or "review" not in df_raw.columns:
        print("エラー: レビューデータが空であるか、'review' 列が存在しません。")
        return

    # 実際の抽出データからランダムに10件取得
    actual_sample_size = min(sample_size, len(df_raw))
    df_sample = df_raw.sample(n=actual_sample_size, random_state=42).reset_index(drop=True)
    print(f"データからランダムに {actual_sample_size} 件のレビューを抽出し、分析を開始します。")

    analyzer = EmotionAnalyzer()
    df_analyzed = analyzer.analyze_dataframe(df_sample, text_column="review")

    # 結果をCSV保存 (UTF-8 with BOM でExcel等での文字化けを防止)
    os.makedirs(os.path.dirname(output_csv), exist_ok=True)
    df_analyzed.to_csv(output_csv, index=False, encoding="utf-8-sig")
    print(f"\n分析結果をCSVとして保存しました: {output_csv}")

    # シェルへの簡略サマリー出力
    print("\n" + "=" * 80)
    print(f"【感情分析結果サマリー (ランダム抽出 {actual_sample_size}件)】")
    print("=" * 80)

    for idx, row in df_analyzed.iterrows():
        game_title = row.get("game_title", row.get("appid", "Unknown Game"))
        review_text = str(row["review"]).replace("\n", " ")
        short_text = (review_text[:60] + "...") if len(review_text) > 60 else review_text

        print(f"\n[{idx + 1}/{actual_sample_size}] ゲーム: {game_title}")
        print(f"  レビュー: \"{short_text}\"")
        print(f"  主要感情: 【{row['primary_emotion']}】")
        print(f"  感情ランキング: {row['emotion_ranking']}")

        # 6感情の割合(%)を1行表示
        ratios = [f"{e}:{row[f'ratio_{e}_pct']}%" for e in MAIN_EMOTIONS_JP]
        print(f"  感情割合(%): " + " | ".join(ratios))

    print("\n" + "=" * 80)
    print(f"詳細なCSVデータ出力先: '{output_csv}'")


if __name__ == "__main__":
    main()
