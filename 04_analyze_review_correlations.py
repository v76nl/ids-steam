import os
import numpy as np
import pandas as pd

# 6つの主要感情
MAIN_EMOTIONS = ["喜び", "悲しみ", "怒り", "恐怖", "驚き", "嫌悪"]
EMOTION_RATIO_COLS = [f"ratio_{e}_pct" for e in MAIN_EMOTIONS]
EMOTION_SCORE_COLS = [f"score_{e}" for e in MAIN_EMOTIONS]


def analyze_recommendation_comparison(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    高評価 (Recommended) vs 低評価 (Not Recommended) の感情構造の比較分析
    """
    print("\n" + "=" * 80)
    print("【分析1: 高評価 (Recommended) vs 低評価 (Not Recommended) の感情比較】")
    print("=" * 80)

    # recommend列のクリーニング
    df_clean = df.dropna(subset=["recommend"]).copy()
    df_clean["recommend_clean"] = df_clean["recommend"].astype(str).str.strip()

    rec_group = df_clean.groupby("recommend_clean")

    # 1-1. 各感情の平均割合(%)
    ratio_summary = rec_group[EMOTION_RATIO_COLS].mean().round(2)
    count_summary = rec_group.size().rename("件数")
    summary_df = pd.concat([count_summary, ratio_summary], axis=1)

    print("\n--- 1. おすすめ別 6感情平均割合(%) ---")
    print(summary_df.to_string())

    # 1-2. 主要感情 (primary_emotion) の分布割合(%)
    primary_dist = (
        pd.crosstab(df_clean["recommend_clean"], df_clean["primary_emotion"], normalize="index") * 100
    ).round(2)

    print("\n--- 2. おすすめ別 主要感情 (primary_emotion) 出現頻度(%) ---")
    print(primary_dist.to_string())

    return summary_df, primary_dist


def analyze_playtime_correlations(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    プレイ時間 (playtime) と 6感情の相関・カテゴリ別集計分析
    """
    print("\n" + "=" * 80)
    print("【分析2: プレイ時間 (playtime) と感情の相関・推移分析】")
    print("=" * 80)

    df_play = df.copy()
    df_play["playtime"] = pd.to_numeric(df_play["playtime"], errors="coerce")
    df_play = df_play.dropna(subset=["playtime"])
    df_play = df_play[df_play["playtime"] >= 0]

    # 2-1. プレイ時間の相関係数 (Pearson & Spearman)
    corr_records = []
    for emotion in MAIN_EMOTIONS:
        score_col = f"score_{emotion}"
        ratio_col = f"ratio_{emotion}_pct"
        pearson_ratio = df_play["playtime"].corr(df_play[ratio_col], method="pearson")
        spearman_ratio = df_play["playtime"].rank().corr(df_play[ratio_col].rank())
        corr_records.append({
            "感情": emotion,
            "相関係数 (Pearson)": round(pearson_ratio, 4),
            "順位相関 (Spearman)": round(spearman_ratio, 4)
        })

    corr_df = pd.DataFrame(corr_records).set_index("感情")
    print("\n--- 1. プレイ時間と感情割合(%)の相関係数 ---")
    print(corr_df.to_string())

    # 2-2. プレイ時間のバケット分け集計
    bins = [-1, 2, 10, 30, 100, float("inf")]
    labels = ["極短時間 (0-2h)", "短時間 (2-10h)", "中時間 (10-30h)", "長時間 (30-100h)", "ヘビー (100h+)"]
    df_play["playtime_bucket"] = pd.cut(df_play["playtime"], bins=bins, labels=labels)

    bucket_group = df_play.groupby("playtime_bucket", observed=False)
    bucket_ratio = bucket_group[EMOTION_RATIO_COLS].mean().round(2)
    bucket_counts = bucket_group.size().rename("件数")
    avg_playtime = bucket_group["playtime"].mean().round(1).rename("平均時間(h)")

    bucket_summary = pd.concat([bucket_counts, avg_playtime, bucket_ratio], axis=1)

    print("\n--- 2. プレイ時間帯別 6感情平均割合(%) ---")
    print(bucket_summary.to_string())

    return corr_df, bucket_summary


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

    # 分析1: おすすめ比較
    rec_summary, primary_dist = analyze_recommendation_comparison(df)
    rec_summary.to_csv(os.path.join(output_dir, "recommend_ratio_summary.csv"), encoding="utf-8-sig")
    primary_dist.to_csv(os.path.join(output_dir, "recommend_primary_dist.csv"), encoding="utf-8-sig")

    # 分析2: プレイ時間相関
    corr_df, bucket_summary = analyze_playtime_correlations(df)
    corr_df.to_csv(os.path.join(output_dir, "playtime_correlations.csv"), encoding="utf-8-sig")
    bucket_summary.to_csv(os.path.join(output_dir, "playtime_bucket_summary.csv"), encoding="utf-8-sig")

    print("\n" + "=" * 80)
    print(f"分析完了！集計テーブルを '{output_dir}' ディレクトリへ出力しました。")
    print("=" * 80)


if __name__ == "__main__":
    main()
