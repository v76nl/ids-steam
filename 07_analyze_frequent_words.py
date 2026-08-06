import os
import re
from collections import Counter

import MeCab
import pandas as pd
import unidic_lite
from tqdm import tqdm


def is_stopword(word: str) -> bool:
    stopwords = {
        'こと', 'もの', 'これ', 'それ', 'あれ', 'どれ', 'よう', 'ため', 'ん', 'の',
        'ほう', 'ところ', 'わけ', 'はず', 'うち', 'そう', 'さん'
    }
    if word in stopwords:
        return True

    if len(word) == 1 and re.match(r'^[ぁ-んァ-ヶー・]$', word):
        return True

    return bool(re.match(r'^[0-9０-９]+$', word))


def extract_words(text: str, tagger: MeCab.Tagger) -> tuple[list[str], list[str]]:
    if not isinstance(text, str) or not text.strip():
        return [], []

    nouns = []
    adjectives = []
    current_compound = []

    try:
        node = tagger.parseToNode(text)
        while node:
            if not node.surface:
                node = node.next
                continue

            features = node.feature.split(',')
            pos = features[0]
            pos_detail = features[1] if len(features) > 1 else ''

            if pos == '名詞' and pos_detail not in ['代名詞', '数詞']:
                current_compound.append(node.surface)
            else:
                if current_compound:
                    compound_word = ''.join(current_compound)
                    if not is_stopword(compound_word):
                        nouns.append(compound_word)
                    current_compound = []

                if pos == '形容詞':
                    base_form = features[7] if len(features) > 7 and features[7] != '*' else node.surface
                    if not is_stopword(base_form):
                        adjectives.append(base_form)

            node = node.next

        if current_compound:
            compound_word = ''.join(current_compound)
            if not is_stopword(compound_word):
                nouns.append(compound_word)
    except Exception:
        pass

    return nouns, adjectives


def get_top_df(counter: Counter, prefix: str, total_reviews: int) -> pd.DataFrame:
    top_items = counter.most_common(100)
    data = []
    for word, count in top_items:
        pct = round((count / total_reviews) * 100, 2)
        data.append((word, count, pct))
    return pd.DataFrame(data, columns=[f'{prefix}_word', f'{prefix}_count', f'{prefix}_pct'])


def main():
    print('Loading data...')
    df = pd.read_csv('data/japanese_steam_reviews_emotions.csv')

    tagger = MeCab.Tagger(f'-d {unidic_lite.DICDIR}')

    all_nouns_counter = Counter()
    rec_nouns_counter = Counter()
    not_rec_nouns_counter = Counter()

    all_adjs_counter = Counter()
    rec_adjs_counter = Counter()
    not_rec_adjs_counter = Counter()

    reviews = df['review'].tolist()
    recommends = df.get('recommend', pd.Series(['Recommended'] * len(df))).tolist()

    total_all = len(df)
    total_rec = sum(1 for r in recommends if r == 'Recommended')
    total_not_rec = total_all - total_rec

    print(f'Total reviews: {total_all:,} (Recommended: {total_rec:,}, Not Recommended: {total_not_rec:,})')

    print('Extracting nouns and adjectives (Full text parsing without character limit)...')
    for review, recommend in tqdm(zip(reviews, recommends), total=len(df)):
        nouns, adjs = extract_words(review, tagger)

        all_nouns_counter.update(nouns)
        all_adjs_counter.update(adjs)

        if recommend == 'Recommended':
            rec_nouns_counter.update(nouns)
            rec_adjs_counter.update(adjs)
        else:
            not_rec_nouns_counter.update(nouns)
            not_rec_adjs_counter.update(adjs)

    print('Counting frequencies and saving...')
    df_nouns_result = pd.concat(
        [
            get_top_df(all_nouns_counter, 'all', total_all),
            get_top_df(rec_nouns_counter, 'rec', total_rec),
            get_top_df(not_rec_nouns_counter, 'not_rec', total_not_rec),
        ],
        axis=1,
    )
    nouns_out_path = 'data/insights/frequent_nouns.csv'
    os.makedirs('data/insights', exist_ok=True)
    df_nouns_result.to_csv(nouns_out_path, index=False)
    print(f'Frequent nouns saved to {nouns_out_path}')

    df_adjs_result = pd.concat(
        [
            get_top_df(all_adjs_counter, 'all', total_all),
            get_top_df(rec_adjs_counter, 'rec', total_rec),
            get_top_df(not_rec_adjs_counter, 'not_rec', total_not_rec),
        ],
        axis=1,
    )
    adjs_out_path = 'data/insights/frequent_adjectives.csv'
    df_adjs_result.to_csv(adjs_out_path, index=False)
    print(f'Frequent adjectives saved to {adjs_out_path}')

    print('\nTop 10 overall adjectives:')
    print(df_adjs_result[['all_word', 'all_count', 'all_pct']].head(10))


if __name__ == '__main__':
    main()
