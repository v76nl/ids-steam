import argparse
import gc
import logging
import os
import sys

import pandas as pd
import torch
from tqdm import tqdm
from transformers import AutoModelForSequenceClassification, AutoTokenizer

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
    "trust": "信頼",
}

MAIN_EMOTIONS_JP = [EMOTION_LABELS_JP[e] for e in EKMAN_EMOTIONS]


def setup_logger(log_file: str):
    logger = logging.getLogger("EmotionAnalyzer")
    logger.setLevel(logging.INFO)
    formatter = logging.Formatter(
        "[%(asctime)s][%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )

    # ログファイル出力
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    # 標準出力
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    return logger


class EmotionAnalyzer:
    def __init__(
        self, model_name: str = "neuralnaut/deberta-wrime-emotions", logger=None
    ):
        self.logger = logger or logging.getLogger("EmotionAnalyzer")
        self.logger.info(f"感情分析モデル ({model_name}) を初期化中……")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

        # CPUマルチスレッド最適化 (Intel Xeon Sapphire Rapids 8コア対応)
        if self.device == "cpu":
            num_cores = os.cpu_count() or 8
            torch.set_num_threads(num_cores)
            self.logger.info(
                f"PyTorch CPU並列処理スレッド数を {num_cores} に設定しました (Intel AMX / AVX-512 最適化)"
            )

        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name).to(
            self.device
        )
        self.model.eval()

        self.id2label = self.model.config.id2label
        self.logger.info(f"モデル初期化完了 (使用デバイス: {self.device})")

    def process_batch(self, batch_texts: list) -> list:
        inputs = self.tokenizer(
            batch_texts,
            return_tensors="pt",
            truncation=True,
            padding=True,
            max_length=512,
        ).to(self.device)

        with torch.no_grad():
            outputs = self.model(**inputs)
            scores_batch = torch.sigmoid(outputs.logits).cpu().numpy()

        results = []
        for scores in scores_batch:
            record = {}
            for idx, score in enumerate(scores):
                raw_label = self.id2label.get(idx, f"label_{idx}").lower()
                jp_label = EMOTION_LABELS_JP.get(raw_label, raw_label)
                record[jp_label] = float(score)
            results.append(record)
        return results

    def analyze_dataframe_incremental(
        self,
        df: pd.DataFrame,
        output_csv: str,
        text_column: str = "review",
        batch_size: int = 64,
        save_interval: int = 1000,
        start_index: int = 0,
    ):
        total_items = len(df)
        self.logger.info(
            f"処理対象件数: {total_items} 件 (開始位置: {start_index} 件目から)"
        )

        is_first_write = (start_index == 0) or (not os.path.exists(output_csv))
        texts = df[text_column].fillna("").astype(str).tolist()

        buffer_rows = []

        with tqdm(
            total=total_items, initial=start_index, desc="感情分析進捗", unit="件"
        ) as pbar:
            for i in range(start_index, total_items, batch_size):
                batch_end = min(i + batch_size, total_items)
                batch_texts = texts[i:batch_end]
                batch_df = df.iloc[i:batch_end].copy()

                try:
                    scores_records = self.process_batch(batch_texts)
                    scores_df = pd.DataFrame(scores_records)

                    for emotion in MAIN_EMOTIONS_JP:
                        if emotion in scores_df.columns:
                            batch_df[f"score_{emotion}"] = scores_df[
                                emotion
                            ].values.round(4)
                        else:
                            batch_df[f"score_{emotion}"] = 0.0

                    six_scores = batch_df[[f"score_{e}" for e in MAIN_EMOTIONS_JP]]
                    row_sums = six_scores.sum(axis=1).replace(0, 1.0)

                    for emotion in MAIN_EMOTIONS_JP:
                        batch_df[f"ratio_{emotion}_pct"] = (
                            (batch_df[f"score_{emotion}"] / row_sums) * 100
                        ).round(1)

                    batch_df["primary_emotion"] = six_scores.idxmax(axis=1).str.replace(
                        "score_", ""
                    )

                    def get_top_ranking(row):
                        ranked = row.sort_values(ascending=False)
                        return " > ".join(
                            [
                                f"{idx.replace('score_', '')}({val:.2f})"
                                for idx, val in ranked.iloc[:3].items()
                            ]
                        )

                    batch_df["emotion_ranking"] = six_scores.apply(
                        get_top_ranking, axis=1
                    )

                    buffer_rows.append(batch_df)

                except Exception as e:
                    self.logger.error(
                        f"バッチ [{i}:{batch_end}] 処理中にエラーが発生しました: {e}. スキップして続行します。"
                    )

                pbar.update(len(batch_texts))

                # 一定件数ごとにディスク追記保存 & メモリ解放 (OOM防止)
                if (
                    len(buffer_rows) * batch_size >= save_interval
                    or batch_end == total_items
                ):
                    if buffer_rows:
                        chunk_df = pd.concat(buffer_rows, ignore_index=True)
                        chunk_df.to_csv(
                            output_csv,
                            mode="a" if not is_first_write else "w",
                            index=False,
                            header=is_first_write,
                            encoding="utf-8-sig",
                        )
                        is_first_write = False
                        buffer_rows.clear()
                        gc.collect()
                        self.logger.info(
                            f"チェックポイント保存: {batch_end}/{total_items} 件完了 -> '{output_csv}'"
                        )


def main():
    parser = argparse.ArgumentParser(
        description="Steam日本語レビュー 6感情分析スクリプト (VPS長時間バッチ対応版)"
    )
    parser.add_argument(
        "sample_size",
        type=int,
        nargs="?",
        default=None,
        help="分析件数 (未指定の場合は全件分析)",
    )
    parser.add_argument(
        "--batch-size", type=int, default=64, help="推論バッチサイズ (デフォルト: 64)"
    )
    parser.add_argument(
        "--save-interval",
        type=int,
        default=100,
        help="中間追記保存の件数インターバル (デフォルト: 100)",
    )
    parser.add_argument(
        "--no-resume", action="store_true", help="途中再開を行わず最初から上書き実行"
    )
    args = parser.parse_args()

    input_csv = "data/japanese_steam_reviews.csv"
    log_file = "data/analyze_emotions.log"
    logger = setup_logger(log_file)

    if not os.path.exists(input_csv):
        logger.error(
            f"入力ファイル '{input_csv}' が存在しません。先に main.py を実行してください。"
        )
        return

    logger.info(f"入力データ '{input_csv}' を読み込んでいます……")
    df_raw = pd.read_csv(input_csv)

    if df_raw.empty or "review" not in df_raw.columns:
        logger.error("エラー: レビューデータが空であるか、'review' 列が存在しません。")
        return

    total_count = len(df_raw)

    if args.sample_size is not None and args.sample_size > 0:
        actual_sample_size = min(args.sample_size, total_count)
        df_target = df_raw.sample(n=actual_sample_size, random_state=42).reset_index(
            drop=True
        )
        output_csv = "data/japanese_steam_reviews_emotion_sample.csv"
        logger.info(
            f"全 {total_count} 件中、指定された {actual_sample_size} 件をサンプリング分析します。"
        )
    else:
        df_target = df_raw.reset_index(drop=True)
        actual_sample_size = total_count
        output_csv = "data/japanese_steam_reviews_emotions.csv"
        logger.info(f"全件分析処理を開始します (合計 {total_count} 件)。")

    # チェックポイント（途中再開）機能
    start_index = 0
    if not args.no_resume and os.path.exists(output_csv):
        try:
            existing_df = pd.read_csv(output_csv)
            start_index = len(existing_df)
            if start_index >= actual_sample_size:
                logger.info(
                    f"すでに全処理 ({start_index}/{actual_sample_size} 件) が完了しています。'{output_csv}' をご確認ください。"
                )
                return
            logger.info(
                f"既存の出力ファイル '{output_csv}' を検出しました。{start_index} 件目から処理を自動再開します。"
            )
        except Exception as err:
            logger.warning(
                f"既存出力ファイルの読み込みに失敗したため、最初から実行します: {err}"
            )
            start_index = 0

    analyzer = EmotionAnalyzer(logger=logger)
    analyzer.analyze_dataframe_incremental(
        df_target,
        output_csv=output_csv,
        text_column="review",
        batch_size=args.batch_size,
        save_interval=args.save_interval,
        start_index=start_index,
    )

    logger.info(f"すべての処理が完了しました。出力ファイル: '{output_csv}'")


if __name__ == "__main__":
    main()
