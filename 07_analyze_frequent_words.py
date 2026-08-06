import os
import re
from collections import Counter

import MeCab
import pandas as pd
import unidic_lite
from tqdm import tqdm


def is_stopword(word: str) -> bool:
    """
    ストップワードを除外する
    """
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
    }
    if word in stopwords:
        return True

    # 1文字のひらがな・カタカナ・記号的なものは除外
    if len(word) == 1 and re.match(r"^[ぁ-んァ-ヶー・]$", word):
        return True

    # 数値のみの単語も除外
    return bool(re.match(r"^[0-9０-９]+$", word))


def extract_nouns(text: str, tagger: MeCab.Tagger) -> list[str]:
    """
    テキストから名詞を抽出し、連続する名詞は複合名詞として結合する
    """
    if not isinstance(text, str):
        return []

    node = tagger.parseToNode(text)
    nouns = []
    current_compound = []

    while node:
        # BOS/EOS などの特殊ノードは feature が空白になることがあるのでスキップ
        if not node.surface:
            node = node.next
            continue

        features = node.feature.split(",")
        pos = features[0]
        pos_detail = features[1] if len(features) > 1 else ""

        # === ここから連節処理のロジック ===
        # 名詞（代名詞・数詞などは除く）を対象とし、連続して出現した場合はバッファに溜める
        if pos == "名詞" and pos_detail not in ["代名詞", "数詞"]:
            current_compound.append(node.surface)
        else:
            # TODO: 将来的には形容詞（「面白い」「高い」など）の頻出語集計も追加する
            # elif pos == "形容詞":
            #     adjectives.append(node.surface)

            # 名詞以外の品詞が来た時点で、これまで連続していた名詞群（バッファ）を結合して1つの複合名詞とする
            if current_compound:
                compound_word = "".join(current_compound)
                if not is_stopword(compound_word):
                    nouns.append(compound_word)
                current_compound = []
        # === 連節処理 ここまで ===

        node = node.next

    # ループ終了時にバッファに残っている複合名詞を処理
    if current_compound:
        compound_word = "".join(current_compound)
        if not is_stopword(compound_word):
            nouns.append(compound_word)

    return nouns


def main():
    print("Loading data...")
    df = pd.read_csv("data/japanese_steam_reviews_emotions.csv")

    # MeCabの初期化
    tagger = MeCab.Tagger(f"-d {unidic_lite.DICDIR}")

    all_nouns = []
    recommended_nouns = []
    not_recommended_nouns = []

    print("Extracting nouns...")
    # tqdmで進捗を表示
    for _, row in tqdm(df.iterrows(), total=len(df)):
        review = row["review"]
        recommend = row.get("recommend", "Recommended")

        nouns = extract_nouns(review, tagger)
        all_nouns.extend(nouns)

        if recommend == "Recommended":
            recommended_nouns.extend(nouns)
        else:
            not_recommended_nouns.extend(nouns)

    print("Counting frequencies...")
    all_counter = Counter(all_nouns)
    rec_counter = Counter(recommended_nouns)
    not_rec_counter = Counter(not_recommended_nouns)

    # 上位100件を取得してDataFrame化
    def get_top_df(counter: Counter, prefix: str) -> pd.DataFrame:
        top_items = counter.most_common(100)
        return pd.DataFrame(top_items, columns=[f"{prefix}_word", f"{prefix}_count"])

    df_all = get_top_df(all_counter, "all")
    df_rec = get_top_df(rec_counter, "rec")
    df_not_rec = get_top_df(not_rec_counter, "not_rec")

    # 全体を結合（行数が同じなので横に結合）
    df_result = pd.concat([df_all, df_rec, df_not_rec], axis=1)

    out_path = "data/insights/frequent_nouns.csv"
    os.makedirs("data/insights", exist_ok=True)
    df_result.to_csv(out_path, index=False)

    print("\nTop 10 overall nouns:")
    print(df_all.head(10))

    print(f"\nResults saved to {out_path}")


if __name__ == "__main__":
    main()
