import ast
import os
import re
import pandas as pd

MAIN_EMOTIONS = ["喜び", "悲しみ", "怒り", "恐怖", "驚き", "嫌悪"]
EMOTION_RATIO_COLS = [f"ratio_{e}_pct" for e in MAIN_EMOTIONS]


def parse_genres(genre_str):
    if not isinstance(genre_str, str) or not genre_str.strip():
        return []
    try:
        parsed = ast.literal_eval(genre_str)
        if isinstance(parsed, list):
            return [str(g).strip() for g in parsed if g]
    except Exception:
        pass
    cleaned = re.sub(r"[\[\]'\"]", "", genre_str)
    return [g.strip() for g in cleaned.split(",") if g.strip()]


def analyze_genre_playtime_correlations(df: pd.DataFrame) -> pd.DataFrame:
    """
    ジャンル別のプレイ時間 (playtime) と 6感情の相関分析
    """
    print("\n" + "=" * 80)
    print("【分析4: ジャンル別 プレイ時間 (playtime) と 6感情の相関分析】")
    print("=" * 80)

    df_clean = df.dropna(subset=["genres", "playtime"]).copy()
    df_clean["playtime"] = pd.to_numeric(df_clean["playtime"], errors="coerce")
    df_clean = df_clean.dropna(subset=["playtime"])
    df_clean = df_clean[df_clean["playtime"] >= 0]

    df_clean["parsed_genres"] = df_clean["genres"].apply(parse_genres)
    df_exploded = df_clean.explode("parsed_genres").reset_index(drop=True)
    df_exploded = df_exploded[df_exploded["parsed_genres"].str.len() > 0]

    genre_counts = df_exploded["parsed_genres"].value_counts()
    top_genres = genre_counts.head(12).index.tolist()

    records = []
    for genre in top_genres:
        genre_df = df_exploded[df_exploded["parsed_genres"] == genre]
        count = len(genre_df)
        avg_playtime = round(genre_df["playtime"].mean(), 1)
        median_playtime = round(genre_df["playtime"].median(), 1)

        record = {
            "ジャンル": genre,
            "件数": count,
            "平均時間(h)": avg_playtime,
            "中央値時間(h)": median_playtime
        }

        # 6感情それぞれの順位相関 (Spearman)
        for emotion in MAIN_EMOTIONS:
            ratio_col = f"ratio_{emotion}_pct"
            spearman_corr = genre_df["playtime"].rank().corr(genre_df[ratio_col].rank())
            record[f"{emotion} (Spearman)"] = round(spearman_corr, 4)

        records.append(record)

    corr_df = pd.DataFrame(records).set_index("ジャンル")

    print("\n--- 主要ジャンル別 プレイ時間 vs 6感情順位相関 (Spearman) ---")
    print(corr_df.to_string())

    return corr_df


def main():
    input_csv = "data/japanese_steam_reviews_emotions.csv"
    output_dir = "data/insights"
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.exists(input_csv):
        print(f"エラー: データファイル '{input_csv}' が見つかりません。")
        return

    print(f"データファイル '{input_csv}' を読み込んでいます……")
    df = pd.read_csv(input_csv)
    print(f"読込完了: 全 {len(df):,} 件")

    corr_df = analyze_genre_playtime_correlations(df)
    corr_df.to_csv(os.path.join(output_dir, "genre_playtime_correlations.csv"), encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print(f"ジャンル別プレイ時間相関分析完了！結果を '{output_dir}/genre_playtime_correlations.csv' へ出力しました。")
    print("=" * 80)


if __name__ == "__main__":
    main()
