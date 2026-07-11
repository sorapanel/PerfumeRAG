"""JSONを読み込み、テキスト変換してChromaDBに登録するモジュール。"""

import json
import os
from pathlib import Path

import chromadb
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from dotenv import load_dotenv

load_dotenv()

COLLECTION_NAME = "perfumes"
DEFAULT_EMBED_MODEL = "intfloat/multilingual-e5-base"


def load_json(path: str) -> list[dict]:
    """JSONファイルを読み込む。

    Args:
        path: JSONファイルのパス

    Returns:
        香水データのリスト

    Raises:
        FileNotFoundError: ファイルが存在しない場合
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"JSONファイルが見つかりません: {path}")
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def perfume_to_text(perfume: dict) -> str:
    """香水データをSPEC.mdのテンプレートに従いテキストに変換する。

    Args:
        perfume: 香水データの辞書

    Returns:
        変換されたテキスト
    """
    return (
        f"名前: {perfume.get('titleJp', '')}（{perfume.get('title', '')}）\n"
        f"ブランド: {perfume.get('brand', '')}\n"
        f"コンセプト: {perfume.get('concept', '')}\n"
        f"トップノート: {', '.join(perfume.get('top', []))}\n"
        f"ミドルノート: {', '.join(perfume.get('middle', []))}\n"
        f"ラストノート: {', '.join(perfume.get('last', []))}\n"
        f"イメージ: {', '.join(perfume.get('imagery', []))}\n"
        f"印象: {', '.join(perfume.get('impression', []))}\n"
        f"シーン: {', '.join(perfume.get('scenes', []))}\n"
        f"季節: {', '.join(perfume.get('season', []))}"
    )


def build_metadata(perfume: dict) -> dict:
    """ChromaDB登録用のメタデータを構築する。

    ChromaDB 1.x は $contains が非対応のため、季節・シーンごとにブール型フラグも追加する。

    Args:
        perfume: 香水データの辞書

    Returns:
        メタデータの辞書
    """
    seasons = perfume.get("season", [])
    scenes = perfume.get("scenes", [])

    meta: dict = {
        "brand": perfume.get("brand", ""),
        "season": ",".join(seasons),
        "scenes": ",".join(scenes),
        "imagery": ",".join(perfume.get("imagery", [])),
        "impression": ",".join(perfume.get("impression", [])),
    }

    # フィルタ用ブール型フラグ
    for s in ["春", "夏", "秋", "冬"]:
        meta[f"season_{s}"] = s in seasons
    for sc in scenes:
        meta[f"scene_{sc}"] = True

    return meta


def build_index(json_path: str, chroma_path: str) -> None:
    """JSONを読み込み、ベクトルDBにインデックスを構築する。

    Args:
        json_path: 香水JSONファイルのパス
        chroma_path: ChromaDBの永続化パス

    Raises:
        FileNotFoundError: JSONファイルが存在しない場合
        ConnectionError: ChromaDBへの接続に失敗した場合
    """
    perfumes = load_json(json_path)

    embed_model = os.getenv("EMBED_MODEL", DEFAULT_EMBED_MODEL)
    embedding_fn = SentenceTransformerEmbeddingFunction(model_name=embed_model)

    try:
        client = chromadb.PersistentClient(path=chroma_path)
        collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
        )
    except Exception as e:
        raise ConnectionError(f"ChromaDBへの接続に失敗しました: {e}") from e

    ids = []
    documents = []
    metadatas = []

    seen: set[str] = set()
    for perfume in perfumes:
        title = perfume.get("title", "")
        brand = perfume.get("brand", "")
        if not title:
            continue
        # title が重複する場合は brand を付加してユニークにする
        doc_id = f"{title}__{brand}" if title in seen else title
        seen.add(title)
        ids.append(doc_id)
        documents.append(perfume_to_text(perfume))
        metadatas.append(build_metadata(perfume))

    collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
    print(f"{len(ids)} 件の香水データをインデックスに登録しました。")
