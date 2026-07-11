"""ingest.py のテスト。"""

import json
import tempfile
from pathlib import Path

import pytest

from perfume_rag.ingest import build_metadata, load_json, perfume_to_text

SAMPLE_PERFUME = {
    "title": "Test Perfume",
    "titleJp": "テスト香水",
    "brand": "TestBrand",
    "concept": "テスト用のコンセプト文",
    "top": ["ベルガモット", "レモン"],
    "middle": ["ローズ", "ジャスミン"],
    "last": ["ムスク", "サンダルウッド"],
    "imagery": ["エレガント", "フレッシュ"],
    "impression": ["ナチュラル"],
    "scenes": ["オフィス", "デート"],
    "season": ["春", "夏"],
}


def test_load_json_ok(tmp_path: Path) -> None:
    p = tmp_path / "test.json"
    p.write_text(json.dumps([SAMPLE_PERFUME]), encoding="utf-8")
    data = load_json(str(p))
    assert len(data) == 1
    assert data[0]["title"] == "Test Perfume"


def test_load_json_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        load_json("/nonexistent/path/perfumes.json")


def test_perfume_to_text_contains_required_fields() -> None:
    text = perfume_to_text(SAMPLE_PERFUME)
    assert "テスト香水" in text
    assert "Test Perfume" in text
    assert "TestBrand" in text
    assert "テスト用のコンセプト文" in text
    assert "ベルガモット" in text
    assert "ローズ" in text
    assert "ムスク" in text
    assert "エレガント" in text
    assert "ナチュラル" in text
    assert "オフィス" in text
    assert "春" in text


def test_build_metadata_joins_arrays() -> None:
    meta = build_metadata(SAMPLE_PERFUME)
    assert meta["brand"] == "TestBrand"
    assert meta["season"] == "春,夏"
    assert meta["scenes"] == "オフィス,デート"
    assert meta["imagery"] == "エレガント,フレッシュ"
    assert meta["impression"] == "ナチュラル"


def test_build_index(tmp_path: Path) -> None:
    json_path = tmp_path / "perfumes.json"
    json_path.write_text(json.dumps([SAMPLE_PERFUME]), encoding="utf-8")
    chroma_path = str(tmp_path / ".chroma")

    from perfume_rag.ingest import build_index

    build_index(json_path=str(json_path), chroma_path=chroma_path)

    import chromadb
    client = chromadb.PersistentClient(path=chroma_path)
    collection = client.get_collection("perfumes")
    assert collection.count() == 1
