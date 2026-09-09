"""RAGパイプラインの評価指標を計算するモジュール。

Retrieval評価（Recall@k, MRR）とGeneration評価（LLM-as-judgeによる
忠実性・関連性採点）を提供する。検索・生成ロジック自体は
retriever.py / generator.py を再利用し、ここでは持たない。
"""

import json
import os

import anthropic
from dotenv import load_dotenv

from .generator import generate_answer
from .retriever import DEFAULT_TOP_K, PerfumeRetriever

load_dotenv()

JUDGE_MODEL = "claude-sonnet-4-6"
JUDGE_MAX_TOKENS = 512
JUDGE_TEMPERATURE = 0.0

JUDGE_SYSTEM_PROMPT = """あなたは厳格なRAG回答評価者です。
与えられた「検索結果」と「生成された回答」を比較し、以下2点を1〜5の整数で採点してください。

- faithfulness（忠実性）: 回答が検索結果に書かれている内容だけを根拠にしているか。
  検索結果にない情報を作り話している場合は低く採点する。
- relevance（関連性）: 回答がユーザーの質問に実際に答えているか。

出力は説明文なしで、以下のJSON形式のみを返してください。
{"faithfulness": <1-5>, "relevance": <1-5>, "reasoning": "<採点理由を日本語で簡潔に>"}"""


def recall_at_k(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """正解が上位k件（retrieved_ids）に含まれる割合を返す。

    Args:
        retrieved_ids: 検索結果のID列（上位k件）
        relevant_ids: 正解ID集合

    Returns:
        正解のうち検索結果に含まれた割合（0.0〜1.0）
    """
    if not relevant_ids:
        return 0.0
    hit = sum(1 for rid in relevant_ids if rid in retrieved_ids)
    return hit / len(relevant_ids)


def reciprocal_rank(retrieved_ids: list[str], relevant_ids: set[str]) -> float:
    """正解が検索結果の何位に出たかの逆数を返す（Mean Reciprocal Rankの構成要素）。

    Args:
        retrieved_ids: 検索結果のID列（上位k件、順位順）
        relevant_ids: 正解ID集合

    Returns:
        最初に正解が出現した順位の逆数。正解が含まれない場合は0.0
    """
    for rank, rid in enumerate(retrieved_ids, start=1):
        if rid in relevant_ids:
            return 1.0 / rank
    return 0.0


def judge_answer(query: str, retrieved: list[dict], answer: str) -> dict:
    """Claudeを判定者として、生成回答の忠実性・関連性を採点する。

    Args:
        query: ユーザーの質問
        retrieved: retriever.search()の返り値
        answer: generate_answer()が生成した回答

    Returns:
        {"faithfulness": int, "relevance": int, "reasoning": str}
    """
    docs_text = "\n---\n".join(item["document"] for item in retrieved)
    prompt = (
        f"【検索結果】\n{docs_text}\n\n"
        f"【ユーザーの質問】\n{query}\n\n"
        f"【生成された回答】\n{answer}"
    )

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    message = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=JUDGE_MAX_TOKENS,
        temperature=JUDGE_TEMPERATURE,
        system=JUDGE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    raw = message.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.startswith("json"):
            raw = raw[len("json") :]
    # 採点理由などにJSON後ろへ余計な文章が続く場合があるため、
    # 先頭の1つのJSONオブジェクトだけを取り出す。
    start = raw.index("{")
    obj, _ = json.JSONDecoder().raw_decode(raw[start:])
    return obj


def evaluate(
    eval_set: list[dict],
    chroma_path: str,
    k: int = DEFAULT_TOP_K,
    evaluate_generation: bool = True,
) -> dict:
    """golden set全件に対してretrieval評価（と任意でgeneration評価）を行う。

    Args:
        eval_set: [{"query": str, "relevant_ids": list[str], ...}] 形式のgolden set
        chroma_path: ChromaDBの永続化パス
        k: 検索件数
        evaluate_generation: Trueの場合、回答生成とLLM-as-judge採点も行う

    Returns:
        {"per_query": list[dict], "aggregate": dict}
    """
    retriever = PerfumeRetriever(chroma_path=chroma_path)

    per_query = []
    for item in eval_set:
        query = item["query"]
        relevant_ids = set(item["relevant_ids"])

        retrieved = retriever.search(query=query, k=k)
        retrieved_ids = [r["id"] for r in retrieved]

        result = {
            "query": query,
            "relevant_ids": sorted(relevant_ids),
            "retrieved_ids": retrieved_ids,
            "recall": recall_at_k(retrieved_ids, relevant_ids),
            "reciprocal_rank": reciprocal_rank(retrieved_ids, relevant_ids),
        }

        if evaluate_generation:
            answer = generate_answer(query=query, retrieved=retrieved)
            judged = judge_answer(query=query, retrieved=retrieved, answer=answer)
            result["answer"] = answer
            result["faithfulness"] = judged["faithfulness"]
            result["relevance"] = judged["relevance"]
            result["judge_reasoning"] = judged["reasoning"]

        per_query.append(result)

    n = len(per_query)
    aggregate = {
        "n_queries": n,
        "mean_recall": sum(r["recall"] for r in per_query) / n if n else 0.0,
        "mean_mrr": sum(r["reciprocal_rank"] for r in per_query) / n if n else 0.0,
        "hit_rate": sum(1 for r in per_query if r["recall"] > 0) / n if n else 0.0,
    }
    if evaluate_generation:
        aggregate["mean_faithfulness"] = (
            sum(r["faithfulness"] for r in per_query) / n if n else 0.0
        )
        aggregate["mean_relevance"] = sum(r["relevance"] for r in per_query) / n if n else 0.0

    return {"per_query": per_query, "aggregate": aggregate}
