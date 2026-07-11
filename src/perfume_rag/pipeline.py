"""retriever + generator を組み合わせたエンドツーエンドの処理モジュール。"""

import os

from dotenv import load_dotenv

from .generator import generate_answer
from .retriever import DEFAULT_TOP_K, PerfumeRetriever

load_dotenv()

DEFAULT_CHROMA_PATH = ".chroma"


def ask(
    query: str,
    k: int = DEFAULT_TOP_K,
    filters: dict | None = None,
    chroma_path: str | None = None,
) -> str:
    """自然言語クエリに対して香水を検索し、Claudeの回答を返す。

    Args:
        query: ユーザーの質問
        k: 検索件数
        filters: メタデータフィルタ
        chroma_path: ChromaDBの永続化パス（Noneの場合は環境変数またはデフォルト値を使用）

    Returns:
        Claudeが生成した回答文字列
    """
    path = chroma_path or os.getenv("CHROMA_PATH", DEFAULT_CHROMA_PATH)
    retriever = PerfumeRetriever(chroma_path=path)
    retrieved = retriever.search(query=query, k=k, filters=filters)
    return generate_answer(query=query, retrieved=retrieved)
