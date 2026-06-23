import json
import pandas as pd

def load_metadata(json_path):
    # games.jsonを高速検索用の辞書に変換
    metadata_map = {}
    with open(json_path, 'r', encoding='utf-8') as file_obj:
        raw_json = json.load(file_obj)
        
        if isinstance(raw_json, list):
            for item in raw_json:
                app_id = str(item.get("appid", item.get("AppID", "")))
                metadata_map[app_id] = {
                    "title": item.get("name", item.get("title", "Unknown")),
                    "genres": item.get("genres", [])
                }
        elif isinstance(raw_json, dict):
            for app_id, item in raw_json.items():
                metadata_map[str(app_id)] = {
                    "title": item.get("name", item.get("title", "Unknown")),
                    "genres": item.get("genres", [])
                }
    return metadata_map

def read_csv_safely(file_path, encodings_to_try=None):
    # 複数の文字コードを試してデータフレームを安全に読み込む
    if encodings_to_try is None:
        encodings_to_try = ["utf-8", "ISO-8859-1", "cp1252", "utf-8-sig"]
        
    for encoding_type in encodings_to_try:
        try:
            reviews_df = pd.read_csv(file_path, encoding=encoding_type)
            return reviews_df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    return None

def apply_japanese_filter(reviews_df):
    # 高精度日本語判定ロジックを適用してマスクを返す
    if reviews_df is None or reviews_df.empty or 'review' not in reviews_df.columns:
        return pd.Series([False] * len(reviews_df)) if reviews_df is not None else None

    # レビュー本文の列から欠損値を除外するための準備
    review_series = reviews_df['review'].fillna("")
    
    has_continuous_hiragana = review_series.str.contains(r'[\u3040-\u309F]{2,}', regex=True)
    kana_character_count = review_series.str.count(r'[\u3040-\u309F\u30A0-\u30FF]')
    total_review_length = review_series.str.len().replace(0, 1)
    kana_density_ratio = kana_character_count / total_review_length
    
    is_japanese_mask = has_continuous_hiragana & (kana_character_count >= 10) & (kana_density_ratio >= 0.05)
    return is_japanese_mask