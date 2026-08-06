import ast
import os
import re
import pandas as pd

# 6つの主要感情
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
    # フォールバック: カンマ・シングルクォート除去
    cleaned = re.sub(r"[\[\]'\"]", "", genre_str)
    return [g.strip() for g in cleaned.split(",") if g.strip()]


def analyze_genre_emotions(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    ゲームジャンル（genres）別の 6感情プロファイル分析
    """
    print("\n" + "=" * 80)
    print("【分析3: ゲームジャンル (genres) 別の感情プロファイル分析】")
    print("=" * 80)

    df_clean = df.dropna(subset=["genres"]).copy()
    df_clean["parsed_genres"] = df_clean["genres"].apply(parse_genres)

    # リストを展開 (explode)
    df_exploded = df_clean.explode("parsed_genres")
    df_exploded = df_exploded[df_exploded["parsed_genres"].str.len() > 0]

    # 件数の多い主要ジャンル（上位15ジャンル）を抽出
    genre_counts = df_exploded["parsed_genres"].value_counts()
    top_genres = genre_counts.head(15).index.tolist()

    df_top_genres = df_exploded[df_exploded["parsed_genres"].isin(top_genres)].copy().reset_index(drop=True)

    # ジャンル別集計 (平均感情割合 & おすすめ度)
    genre_group = df_top_genres.groupby("parsed_genres", observed=False)

    counts = genre_group.size().rename("件数")
    rec_ratios = (
        (genre_group["recommend"].apply(lambda x: (x == "Recommended").mean()) * 100)
        .round(1)
        .rename("Recommended割合(%)")
    )
    emotion_means = genre_group[EMOTION_RATIO_COLS].mean().round(2)

    summary_df = pd.concat([counts, rec_ratios, emotion_means], axis=1).sort_values("件数", ascending=False)

    print("\n--- 1. 主要ジャンル別 6感情平均割合(%) ---")
    print(summary_df.to_string())

    # ジャンル別 主要感情 (primary_emotion) 出現分布(%)
    primary_dist = (
        pd.crosstab(df_top_genres["parsed_genres"], df_top_genres["primary_emotion"], normalize="index") * 100
    ).round(2)

    primary_dist = primary_dist.loc[summary_df.index]

    print("\n--- 2. 主要ジャンル別 第1位感情 (primary_emotion) 分布(%) ---")
    print(primary_dist.to_string())

    return summary_df, primary_dist


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

    genre_summary, genre_primary_dist = analyze_genre_emotions(df)

    genre_summary.to_csv(os.path.join(output_dir, "genre_emotion_summary.csv"), encoding="utf-8-sig")
    genre_primary_dist.to_csv(os.path.join(output_dir, "genre_primary_dist.csv"), encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print(f"ジャンル別感情分析完了！集計結果を '{output_dir}' へ出力しました。")
    print("=" * 80)


if __name__ == "__main__":
    main()
