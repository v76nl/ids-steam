import os
import re
from collections import Counter

import MeCab
import pandas as pd
import unidic_lite
from tqdm import tqdm


def is_stopword(word: str) -> bool:
    stopwords = {
        "こと",
        "もの",
        "これ",
        "それ",
        "あれ",
        "どれ",
        "よう",
        "ため",
        "ん",
        "の",
        "ほう",
        "ところ",
        "わけ",
        "はず",
        "うち",
        "そう",
        "さん",
    }
    if word in stopwords:
        return True

    if len(word) == 1 and re.match(r"^[ぁ-んァ-ヶー・]$", word):
        return True

    return bool(re.match(r"^[0-9０-９]+$", word))


def extract_unique_words(text: str, tagger: MeCab.Tagger) -> tuple[set[str], set[str]]:
    if not isinstance(text, str) or not text.strip():
        return set(), set()

    nouns = set()
    adjectives = set()
    current_compound = []

    try:
        node = tagger.parseToNode(text)
        while node:
            if not node.surface:
                node = node.next
                continue

            features = node.feature.split(",")
            pos = features[0]
            pos_detail = features[1] if len(features) > 1 else ""

            if pos == "名詞" and pos_detail not in ["代名詞", "数詞"]:
                current_compound.append(node.surface)
            else:
                if current_compound:
                    compound_word = "".join(current_compound)
                    if not is_stopword(compound_word):
                        nouns.add(compound_word)
                    current_compound = []

                if pos == "形容詞":
                    base_form = (
                        features[7]
                        if len(features) > 7 and features[7] != "*"
                        else node.surface
                    )
                    if not is_stopword(base_form):
                        adjectives.add(base_form)

            node = node.next

        if current_compound:
            compound_word = "".join(current_compound)
            if not is_stopword(compound_word):
                nouns.add(compound_word)
    except Exception:
        pass

    return nouns, adjectives


def get_top_df(
    counter_all: Counter,
    counter_rec: Counter,
    counter_not_rec: Counter,
    n_all: int,
    n_rec: int,
    n_not_rec: int,
    prefix: str,
) -> pd.DataFrame:
    top_items = counter_all.most_common(100)
    data = []
    for word, _ in top_items:
        a = counter_rec[word]
        c = counter_not_rec[word]
        b = n_rec - a
        d = n_not_rec - c

        pct_all = round(((a + c) / n_all) * 100, 2)
        pct_rec = round((a / n_rec) * 100, 2)
        pct_not_rec = round((c / n_not_rec) * 100, 2)

        # オッズ比 OR (Rec vs NotRec)
        or_val = round((a * d) / (b * c), 2) if (b * c) > 0 else 0.0

        # カイ二乗値 (Chi-squared statistic)
        total = n_all
        chi2 = (
            round(
                total
                * (abs(a * d - b * c) - total / 2) ** 2
                / ((a + b) * (c + d) * (a + c) * (b + d)),
                1,
            )
            if ((a + b) * (c + d) * (a + c) * (b + d)) > 0
            else 0.0
        )

        data.append((word, a + c, pct_all, a, pct_rec, c, pct_not_rec, or_val, chi2))

    return pd.DataFrame(
        data,
        columns=[
            f"{prefix}_word",
            f"{prefix}_count",
            f"{prefix}_coverage_pct",
            "rec_count",
            "rec_coverage_pct",
            "not_rec_count",
            "not_rec_coverage_pct",
            "odds_ratio_rec_vs_not",
            "chi2_stat",
        ],
    )


def main():
    print("Loading data...")
    df = pd.read_csv("data/japanese_steam_reviews_emotions.csv")

    tagger = MeCab.Tagger(f"-d {unidic_lite.DICDIR}")

    all_nouns_counter = Counter()
    rec_nouns_counter = Counter()
    not_rec_nouns_counter = Counter()

    all_adjs_counter = Counter()
    rec_adjs_counter = Counter()
    not_rec_adjs_counter = Counter()

    reviews = df["review"].tolist()
    recommends = df.get("recommend", pd.Series(["Recommended"] * len(df))).tolist()

    total_all = len(df)
    total_rec = sum(1 for r in recommends if r == "Recommended")
    total_not_rec = total_all - total_rec

    print(
        f"Total reviews: {total_all:,} (Recommended: {total_rec:,}, Not Recommended: {total_not_rec:,})"
    )

    print(
        "Extracting unique nouns and adjectives per review (Coverage % & Statistical Tests)..."
    )
    for review, recommend in tqdm(zip(reviews, recommends), total=len(df)):
        nouns, adjs = extract_unique_words(review, tagger)

        all_nouns_counter.update(nouns)
        all_adjs_counter.update(adjs)

        if recommend == "Recommended":
            rec_nouns_counter.update(nouns)
            rec_adjs_counter.update(adjs)
        else:
            not_rec_nouns_counter.update(nouns)
            not_rec_adjs_counter.update(adjs)

    print("Counting frequencies and calculating statistics...")
    df_nouns_result = get_top_df(
        all_nouns_counter,
        rec_nouns_counter,
        not_rec_nouns_counter,
        total_all,
        total_rec,
        total_not_rec,
        "noun",
    )
    nouns_out_path = "data/insights/frequent_nouns.csv"
    os.makedirs("data/insights", exist_ok=True)
    df_nouns_result.to_csv(nouns_out_path, index=False)
    print(f"Frequent nouns saved to {nouns_out_path}")

    df_adjs_result = get_top_df(
        all_adjs_counter,
        rec_adjs_counter,
        not_rec_adjs_counter,
        total_all,
        total_rec,
        total_not_rec,
        "adj",
    )
    adjs_out_path = "data/insights/frequent_adjectives.csv"
    df_adjs_result.to_csv(adjs_out_path, index=False)
    print(f"Frequent adjectives saved to {adjs_out_path}")

    print("\nTop 10 overall adjectives with Coverage % and Odds Ratio:")
    print(
        df_adjs_result[
            [
                "adj_word",
                "adj_count",
                "adj_coverage_pct",
                "odds_ratio_rec_vs_not",
                "chi2_stat",
            ]
        ].head(10)
    )


if __name__ == "__main__":
    main()
