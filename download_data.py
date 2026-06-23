import os
import zipfile
import requests

def download_file(url, save_path):
    # ストリーミング再生でチャンクごとにダウンロード
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    response = requests.get(url, headers=headers, stream=True)
    
    if response.status_code == 200:
        total_size = int(response.headers.get('content-length', 0))
        downloaded_size = 0
        
        with open(save_path, "wb") as file_obj:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    file_obj.write(chunk)
                    downloaded_size += len(chunk)
                    # VPSのログ用に簡易的な進捗を表示
                    if total_size > 0:
                        percent = (downloaded_size / total_size) * 100
                        print(f"ダウンロード進捗: {percent:.1f}% ({downloaded_size // (1024*1024)}MB / {total_size // (1024*1024)}MB)", end="\r")
        print("\nダウンロードが完了しました。")
    else:
        print(f"ダウンロードに失敗しました。ステータスコード: {response.status_code}")

def main():
    metadata_json_url = "https://data.mendeley.com/public-files/datasets/jxy85cr3th/files/9fa9989d-d4f4-426a-aad3-fa9a96700332/file_downloaded"
    reviews_zip_url = "https://data.mendeley.com/public-files/datasets/jxy85cr3th/files/273898e9-90f1-49ff-8d62-df52e67341b3/file_downloaded"

    os.makedirs("data", exist_ok=True)
    json_path = "data/games.json"
    zip_path = "data/steam_data.zip"
    extract_dir = "data/steam_data"

    # games.jsonの取得
    if not os.path.exists(json_path):
        print("games.jsonをダウンロードしています……")
        download_file(metadata_json_url, json_path)
    else:
        print("games.jsonはすでに存在するためスキップします。")

    # steam_data.zipの取得と解凍
    if os.path.exists(extract_dir) and os.listdir(extract_dir):
        print("解凍済みのレビューデータが存在するためスキップします。")
    else:
        if not os.path.exists(zip_path):
            print("レビューのZIPファイルをダウンロードしています……")
            download_file(reviews_zip_url, zip_path)
        
        print("ZIPファイルを解凍しています……")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
        print("解凍が完了しました。")
        
        # 容量削減のためZIP本体は削除
        os.remove(zip_path)

if __name__ == '__main__':
    main()