"""CLIから香水RAGに質問するスクリプト。"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from perfume_rag.pipeline import ask


def build_filters(season: str | None, scene: str | None) -> dict | None:
    """シーズン・シーンのフィルタ辞書を構築する。

    ChromaDB 1.x は $contains 非対応のため、ブール型フラグキーを使用する。
    """
    conditions = []
    if season:
        conditions.append({f"season_{season}": {"$eq": True}})
    if scene:
        conditions.append({f"scene_{scene}": {"$eq": True}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def main() -> None:
    parser = argparse.ArgumentParser(description="香水RAGに質問します")
    parser.add_argument("query", help="質問文")
    parser.add_argument("--top-k", type=int, default=5, help="取得件数（デフォルト: 5）")
    parser.add_argument("--season", help="季節フィルタ（例: 春）")
    parser.add_argument("--scene", help="シーンフィルタ（例: デート）")
    parser.add_argument(
        "--chroma-path",
        default=os.getenv("CHROMA_PATH", ".chroma"),
        help="ChromaDBの永続化パス",
    )
    args = parser.parse_args()

    filters = build_filters(args.season, args.scene)

    print(f"質問: {args.query}")
    if filters:
        print(f"フィルタ: {filters}")
    print("-" * 60)

    try:
        answer = ask(
            query=args.query,
            k=args.top_k,
            filters=filters,
            chroma_path=args.chroma_path,
        )
        print(answer)
    except ConnectionError as e:
        print(f"エラー: {e}", file=sys.stderr)
        print("先に build_index.py を実行してインデックスを構築してください。", file=sys.stderr)
        sys.exit(1)
    except KeyError:
        print("エラー: ANTHROPIC_API_KEY が設定されていません。", file=sys.stderr)
        print(".env ファイルに ANTHROPIC_API_KEY を設定してください。", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
