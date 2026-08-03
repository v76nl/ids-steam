import os
import glob
import re
import pandas as pd
import data_processor

def main():
    json_path = "data/games.json"
    extract_dir = "data/steam_data"
    output_csv = "data/japanese_steam_reviews.csv"

    # 事前にデータが存在するか検証
    if not os.path.exists(json_path) or not os.path.exists(extract_dir):
        print("エラー: データが配置されていません。先に download_data.py を実行してください。")
        return

    # メタデータの読み込み
    print("メタデータを読み込み、高速検索用の辞書を作成しています……")
    metadata_map = data_processor.load_metadata(json_path)
    print(f"{len(metadata_map)}件のゲームデータを辞書化しました。")

    # CSVファイルのリストを取得
    search_path = os.path.join(extract_dir, "**", "*.csv")
    csv_files = glob.glob(search_path, recursive=True)
    print(f"処理対象のCSVファイルは合計 {len(csv_files)} 件です。")

    if os.path.exists(output_csv):
        os.remove(output_csv)
        print("既存の出力ファイルを削除し、初期化しました。")

    is_first_write = True
    processed_file_count = 0

    print("各CSVファイルの個別処理を開始します……")

    for file_path in csv_files:
        filename = os.path.basename(file_path)
        
        match = re.search(r'^(\d+)_', filename)
        app_id = match.group(1) if match else None
        
        if not app_id:
            continue
            
        meta_info = metadata_map.get(app_id, {"title": "Unknown", "genres": []})
        
        # モジュールから安全なCSV読み込み関数を呼び出し
        current_reviews_df = data_processor.read_csv_safely(file_path)
                
        if current_reviews_df is not None and not current_reviews_df.empty:
            current_reviews_df = current_reviews_df.dropna(subset=['review'])
            
            # モジュールから日本語判定フィルターを呼び出し
            is_japanese_mask = data_processor.apply_japanese_filter(current_reviews_df)
            
            if is_japanese_mask is not None:
                japanese_reviews_df = current_reviews_df[is_japanese_mask].copy()
                
                if not japanese_reviews_df.empty:
                    japanese_reviews_df['appid'] = app_id
                    japanese_reviews_df['game_title'] = meta_info['title']
                    japanese_reviews_df['genres'] = str(meta_info['genres'])
                    japanese_reviews_df['source_file'] = filename
                    
                    japanese_reviews_df.to_csv(output_csv, mode='a', index=False, header=is_first_write, encoding='utf-8')
                    is_first_write = False
                    
        processed_file_count += 1
        if processed_file_count % 100 == 0 or processed_file_count == len(csv_files):
            print(f"進捗: {processed_file_count}/{len(csv_files)} ファイルの処理が完了しました……")

    print(f"すべての処理が完了しました。出力先: {output_csv}")

if __name__ == '__main__':
    main()