"""evaluator.py のテスト。"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from perfume_rag.evaluator import evaluate, judge_answer, recall_at_k, reciprocal_rank
from perfume_rag.ingest import build_index

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


def test_recall_at_k_all_found() -> None:
    assert recall_at_k(["A", "B", "C"], {"B"}) == 1.0


def test_recall_at_k_not_found() -> None:
    assert recall_at_k(["A", "B", "C"], {"D"}) == 0.0


def test_recall_at_k_partial() -> None:
    assert recall_at_k(["A", "B"], {"A", "D"}) == 0.5


def test_recall_at_k_empty_relevant() -> None:
    assert recall_at_k(["A"], set()) == 0.0


def test_reciprocal_rank_first_place() -> None:
    assert reciprocal_rank(["A", "B", "C"], {"A"}) == 1.0


def test_reciprocal_rank_second_place() -> None:
    assert reciprocal_rank(["A", "B", "C"], {"B"}) == 0.5


def test_reciprocal_rank_not_found() -> None:
    assert reciprocal_rank(["A", "B", "C"], {"D"}) == 0.0


def _mock_message(text: str) -> MagicMock:
    mock_text = MagicMock()
    mock_text.text = text
    mock_message = MagicMock()
    mock_message.content = [mock_text]
    return mock_message


def test_judge_answer_parses_json() -> None:
    payload = '{"faithfulness": 5, "relevance": 4, "reasoning": "根拠あり"}'
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("perfume_rag.evaluator.anthropic.Anthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_message(payload)

            result = judge_answer("質問", [{"document": "doc"}], "回答")

    assert result == {"faithfulness": 5, "relevance": 4, "reasoning": "根拠あり"}


def test_judge_answer_strips_code_fence() -> None:
    payload = '```json\n{"faithfulness": 3, "relevance": 3, "reasoning": "普通"}\n```'
    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("perfume_rag.evaluator.anthropic.Anthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.return_value = _mock_message(payload)

            result = judge_answer("質問", [{"document": "doc"}], "回答")

    assert result["faithfulness"] == 3


@pytest.fixture()
def chroma_path(tmp_path: Path) -> str:
    json_path = tmp_path / "perfumes.json"
    json_path.write_text(json.dumps(SAMPLE_PERFUMES), encoding="utf-8")
    path = str(tmp_path / ".chroma")
    build_index(json_path=str(json_path), chroma_path=path)
    return path


def test_evaluate_retrieval_only(chroma_path: str) -> None:
    eval_set = [
        {"query": "フローラルな春の香り", "relevant_ids": ["Floral Spring"], "source": "synthetic"},
    ]

    result = evaluate(eval_set, chroma_path=chroma_path, k=2, evaluate_generation=False)

    assert result["aggregate"]["n_queries"] == 1
    assert result["per_query"][0]["recall"] == 1.0
    assert "mean_faithfulness" not in result["aggregate"]


def test_evaluate_with_generation(chroma_path: str) -> None:
    eval_set = [
        {"query": "フローラルな春の香り", "relevant_ids": ["Floral Spring"], "source": "synthetic"},
    ]

    with patch("perfume_rag.evaluator.generate_answer", return_value="おすすめの回答です。"):
        with patch(
            "perfume_rag.evaluator.judge_answer",
            return_value={"faithfulness": 4, "relevance": 5, "reasoning": "妥当"},
        ):
            result = evaluate(eval_set, chroma_path=chroma_path, k=2, evaluate_generation=True)

    assert result["aggregate"]["mean_faithfulness"] == 4.0
    assert result["aggregate"]["mean_relevance"] == 5.0
    assert result["per_query"][0]["answer"] == "おすすめの回答です。"
