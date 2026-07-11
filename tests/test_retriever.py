"""retriever.py のテスト。"""

import json
from pathlib import Path

import pytest

from perfume_rag.ingest import build_index
from perfume_rag.retriever import PerfumeRetriever

SAMPLE_PERFUMES = [
    {
        "title": "Floral Spring",
        "titleJp": "フローラル スプリング",
        "brand": "BrandA",
        "concept": "春らしいフローラルな香り",
        "top": ["ベルガモット"],
        "middle": ["ローズ", "ジャスミン"],
        "last": ["ムスク"],
        "imagery": ["エレガント"],
        "impression": ["ナチュラル"],
        "scenes": ["デート", "オフィス"],
        "season": ["春"],
    },
    {
        "title": "Summer Ocean",
        "titleJp": "サマー オーシャン",
        "brand": "BrandB",
        "concept": "爽やかな海の香り",
        "top": ["シトラス"],
        "middle": ["シーウォーター"],
        "last": ["サンダルウッド"],
        "imagery": ["フレッシュ"],
        "impression": ["クール"],
        "scenes": ["デイリー"],
        "season": ["夏"],
    },
]


@pytest.fixture()
def retriever(tmp_path: Path) -> PerfumeRetriever:
    json_path = tmp_path / "perfumes.json"
    json_path.write_text(json.dumps(SAMPLE_PERFUMES), encoding="utf-8")
    chroma_path = str(tmp_path / ".chroma")
    build_index(json_path=str(json_path), chroma_path=chroma_path)
    return PerfumeRetriever(chroma_path=chroma_path)


def test_search_returns_results(retriever: PerfumeRetriever) -> None:
    results = retriever.search("フローラルな香り", k=2)
    assert len(results) == 2


def test_search_result_structure(retriever: PerfumeRetriever) -> None:
    results = retriever.search("フローラルな香り", k=1)
    result = results[0]
    assert "id" in result
    assert "document" in result
    assert "metadata" in result
    assert "distance" in result


def test_search_top1_is_relevant(retriever: PerfumeRetriever) -> None:
    results = retriever.search("フローラルな春の香り", k=1)
    assert results[0]["id"] == "Floral Spring"


def test_search_with_filter(retriever: PerfumeRetriever) -> None:
    # ChromaDB 1.x は $contains 非対応のため boolean フラグで絞り込む
    results = retriever.search("爽やか", k=2, filters={"season_夏": {"$eq": True}})
    assert all("夏" in r["metadata"]["season"] for r in results)


def test_connection_error_on_invalid_path() -> None:
    with pytest.raises(ConnectionError):
        PerfumeRetriever(chroma_path="/nonexistent/.chroma")
