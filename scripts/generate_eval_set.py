"""香水データからLLM-as-judge用の評価クエリ(golden set)を合成生成するスクリプト。

対象の香水をランダムサンプリングし、Claudeに「その香水を検索させたくなる
自然な質問文（ブランド名・香水名は含めない）」を1件ずつ生成させる。
data/eval_queries.json に既存の "source": "manual" エントリがあれば保持し、
"source": "synthetic" のエントリのみ今回生成した内容で置き換える。
"""

import argparse
import json
import os
import random
import sys

import anthropic
from dotenv import load_dotenv

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from perfume_rag.ingest import load_json  # noqa: E402

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 256
TEMPERATURE = 0.7

SYSTEM_PROMPT = """あなたは香水ECサイトのユーザーになりきる質問生成器です。
与えられた香水の情報（コンセプト・ノート・イメージ・シーン・季節）だけから、
その香水を検索してヒットさせたくなるような、自然な日本語の質問文を1つ作成してください。

制約:
- ブランド名・香水名（英語名/日本語名）は絶対に含めない
- コンセプト文の言い回しをそのまま丸写ししない
- 1〜2文程度の、実際のユーザーが入力しそうな自然な質問にする
- 出力は質問文のみ。説明や前置きは不要"""


def _build_ids(perfumes: list[dict]) -> list[str]:
    """ingest.build_index()と同じルールでドキュメントIDを算出する。"""
    ids = []
    seen: set[str] = set()
    for perfume in perfumes:
        title = perfume.get("title", "")
        brand = perfume.get("brand", "")
        if not title:
            ids.append("")
            continue
        doc_id = f"{title}__{brand}" if title in seen else title
        seen.add(title)
        ids.append(doc_id)
    return ids


def _perfume_summary(perfume: dict) -> str:
    return (
        f"コンセプト: {perfume.get('concept', '')}\n"
        f"トップノート: {', '.join(perfume.get('top', []))}\n"
        f"ミドルノート: {', '.join(perfume.get('middle', []))}\n"
        f"ラストノート: {', '.join(perfume.get('last', []))}\n"
        f"イメージ: {', '.join(perfume.get('imagery', []))}\n"
        f"印象: {', '.join(perfume.get('impression', []))}\n"
        f"シーン: {', '.join(perfume.get('scenes', []))}\n"
        f"季節: {', '.join(perfume.get('season', []))}"
    )


def generate_query_for_perfume(client: anthropic.Anthropic, perfume: dict) -> str:
    """1件の香水データから合成質問文を1件生成する。"""
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": _perfume_summary(perfume)}],
    )
    return message.content[0].text.strip()


def build_synthetic_eval_set(
    data_path: str, n_samples: int, seed: int
) -> list[dict]:
    """香水データをサンプリングし、合成評価クエリのリストを生成する。

    Args:
        data_path: 香水JSONファイルのパス
        n_samples: サンプリングする香水件数
        seed: 乱数シード（再現性確保用）

    Returns:
        [{"query": str, "relevant_ids": [str], "source": "synthetic"}, ...]
    """
    perfumes = load_json(data_path)
    ids = _build_ids(perfumes)
    indexed = [(pid, p) for pid, p in zip(ids, perfumes) if pid]

    rng = random.Random(seed)
    sample = rng.sample(indexed, k=min(n_samples, len(indexed)))

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    entries = []
    for pid, perfume in sample:
        query = generate_query_for_perfume(client, perfume)
        entries.append({"query": query, "relevant_ids": [pid], "source": "synthetic"})
        print(f"生成: {perfume.get('titleJp', pid)} -> {query}")

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="評価用クエリ(golden set)を合成生成します")
    parser.add_argument("--data", default="data/perfumes.json", help="香水JSONファイルのパス")
    parser.add_argument("--n-samples", type=int, default=30, help="サンプリング件数（デフォルト: 30）")
    parser.add_argument("--seed", type=int, default=42, help="乱数シード（デフォルト: 42）")
    parser.add_argument(
        "--output", default="data/eval_queries.json", help="出力先パス（デフォルト: data/eval_queries.json）"
    )
    args = parser.parse_args()

    manual_entries = []
    if os.path.exists(args.output):
        with open(args.output, encoding="utf-8") as f:
            existing = json.load(f)
        manual_entries = [e for e in existing if e.get("source") == "manual"]

    try:
        synthetic_entries = build_synthetic_eval_set(
            data_path=args.data, n_samples=args.n_samples, seed=args.seed
        )
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        sys.exit(1)
    except KeyError:
        print("エラー: ANTHROPIC_API_KEY が設定されていません。", file=sys.stderr)
        sys.exit(1)

    all_entries = manual_entries + synthetic_entries
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(all_entries, f, ensure_ascii=False, indent=2)

    print(
        f"{len(synthetic_entries)}件の合成クエリを生成しました"
        f"（手動キュレーション {len(manual_entries)}件は保持）: {args.output}"
    )


if __name__ == "__main__":
    main()
