"""インデックス構築スクリプト。データ変更時に再実行する。"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from perfume_rag.ingest import build_index


def main() -> None:
    parser = argparse.ArgumentParser(description="香水データのインデックスを構築します")
    parser.add_argument("--data", required=True, help="香水JSONファイルのパス")
    parser.add_argument(
        "--chroma-path",
        default=os.getenv("CHROMA_PATH", ".chroma"),
        help="ChromaDBの永続化パス（デフォルト: .chroma）",
    )
    args = parser.parse_args()

    print(f"インデックス構築を開始します: {args.data}")
    try:
        build_index(json_path=args.data, chroma_path=args.chroma_path)
        print("インデックス構築が完了しました。")
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except ConnectionError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
