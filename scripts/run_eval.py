"""golden setを使ってRAGパイプラインのRetrieval/Generation評価を実行するスクリプト。"""

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from perfume_rag.evaluator import evaluate  # noqa: E402


def print_report(result: dict) -> None:
    agg = result["aggregate"]
    print("=" * 60)
    print(f"評価クエリ数: {agg['n_queries']}")
    print(f"Recall@k (平均): {agg['mean_recall']:.3f}")
    print(f"MRR:            {agg['mean_mrr']:.3f}")
    print(f"Hit Rate:       {agg['hit_rate']:.3f}")
    if "mean_faithfulness" in agg:
        print(f"忠実性 (平均, 1-5): {agg['mean_faithfulness']:.2f}")
        print(f"関連性 (平均, 1-5): {agg['mean_relevance']:.2f}")
    print("=" * 60)

    for r in result["per_query"]:
        print(f"\nQ: {r['query']}")
        print(f"  正解: {r['relevant_ids']}")
        print(f"  検索結果: {r['retrieved_ids']}")
        print(f"  recall={r['recall']:.2f} rr={r['reciprocal_rank']:.2f}", end="")
        if "faithfulness" in r:
            print(f" faithfulness={r['faithfulness']} relevance={r['relevance']}", end="")
        print()


def main() -> None:
    parser = argparse.ArgumentParser(description="RAGパイプラインの評価を実行します")
    parser.add_argument(
        "--eval-set", default="data/eval_queries.json", help="golden setファイルのパス"
    )
    parser.add_argument(
        "--chroma-path",
        default=os.getenv("CHROMA_PATH", ".chroma"),
        help="ChromaDBの永続化パス",
    )
    parser.add_argument("--top-k", type=int, default=5, help="検索件数（デフォルト: 5）")
    parser.add_argument(
        "--no-generation",
        action="store_true",
        help="指定するとGeneration評価（回答生成・LLM-as-judge採点）をスキップする",
    )
    parser.add_argument("--output", help="詳細結果をJSONで保存するパス（任意）")
    args = parser.parse_args()

    if not os.path.exists(args.eval_set):
        print(f"エラー: golden setが見つかりません: {args.eval_set}", file=sys.stderr)
        print("先に scripts/generate_eval_set.py を実行してください。", file=sys.stderr)
        sys.exit(1)

    with open(args.eval_set, encoding="utf-8") as f:
        eval_set = json.load(f)

    try:
        result = evaluate(
            eval_set=eval_set,
            chroma_path=args.chroma_path,
            k=args.top_k,
            evaluate_generation=not args.no_generation,
        )
    except ConnectionError as e:
        print(f"エラー: {e}", file=sys.stderr)
        print("先に build_index.py を実行してインデックスを構築してください。", file=sys.stderr)
        sys.exit(1)
    except KeyError:
        print("エラー: ANTHROPIC_API_KEY が設定されていません。", file=sys.stderr)
        sys.exit(1)

    print_report(result)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"\n詳細結果を保存しました: {args.output}")


if __name__ == "__main__":
    main()
