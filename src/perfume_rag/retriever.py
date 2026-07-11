"""ChromaDBに接続し、クエリに類似した香水を返すモジュール。"""

import os

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "perfumes"
DEFAULT_TOP_K = 5
DEFAULT_EMBED_MODEL = "intfloat/multilingual-e5-base"


class PerfumeRetriever:
    """ChromaDBを使った香水類似検索クラス。"""

    def __init__(self, chroma_path: str) -> None:
        """ChromaDBに接続してコレクションを取得する。

        Args:
            chroma_path: ChromaDBの永続化パス

        Raises:
            ConnectionError: ChromaDBへの接続に失敗した場合
        """
        embed_model = os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL)
        embedding_fn = SentenceTransformerEmbeddingFunction(model_name=embed_model)

        try:
            client = chromadb.PersistentClient(path=chroma_path)
            self._collection = client.get_collection(
                name=COLLECTION_NAME,
                embedding_function=embedding_fn,
            )
        except Exception as e:
            raise ConnectionError(f"ChromaDBへの接続に失敗しました: {e}") from e

    def search(
        self, query: str, k: int = DEFAULT_TOP_K, filters: dict | None = None
    ) -> list[dict]:
        """クエリに類似した香水をk件返す。

        Args:
            query: 検索クエリ文字列
            k: 取得件数
            filters: メタデータフィルタ（ChromaDB のwhere形式）

        Returns:
            検索結果のリスト。各要素は以下のキーを持つ辞書:
            {"id": str, "document": str, "metadata": dict, "distance": float}
        """
        query_params: dict = {
            "query_texts": [query],
            "n_results": k,
        }
        if filters:
            query_params["where"] = filters

        results = self._collection.query(**query_params)

        hits = []
        ids = results.get("ids", [[]])[0]
        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for i, doc_id in enumerate(ids):
            hits.append(
                {
                    "id": doc_id,
                    "document": documents[i],
                    "metadata": metadatas[i],
                    "distance": distances[i],
                }
            )

        return hits
