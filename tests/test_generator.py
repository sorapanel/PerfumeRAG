"""generator.py のテスト。"""

from unittest.mock import MagicMock, patch

from perfume_rag.generator import build_prompt, generate_answer

SAMPLE_RETRIEVED = [
    {
        "id": "Test Perfume",
        "document": "名前: テスト香水（Test Perfume）\nブランド: TestBrand\nコンセプト: テスト用",
        "metadata": {"brand": "TestBrand", "season": "春"},
        "distance": 0.1,
    }
]


def test_build_prompt_contains_query() -> None:
    prompt = build_prompt("春の香水を教えて", SAMPLE_RETRIEVED)
    assert "春の香水を教えて" in prompt


def test_build_prompt_contains_document() -> None:
    prompt = build_prompt("テスト", SAMPLE_RETRIEVED)
    assert "テスト香水" in prompt


def test_build_prompt_multiple_docs_separated() -> None:
    docs = SAMPLE_RETRIEVED + [
        {
            "id": "Another",
            "document": "名前: 別の香水",
            "metadata": {},
            "distance": 0.2,
        }
    ]
    prompt = build_prompt("テスト", docs)
    assert "---" in prompt


def test_generate_answer_returns_string() -> None:
    mock_text = MagicMock()
    mock_text.text = "春に合う香水はこちらです。"
    mock_message = MagicMock()
    mock_message.content = [mock_text]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("perfume_rag.generator.anthropic.Anthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

            result = generate_answer("春の香水", SAMPLE_RETRIEVED)

    assert isinstance(result, str)
    assert result == "春に合う香水はこちらです。"


def test_generate_answer_calls_correct_model() -> None:
    mock_text = MagicMock()
    mock_text.text = "回答"
    mock_message = MagicMock()
    mock_message.content = [mock_text]

    with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "sk-ant-test"}):
        with patch("perfume_rag.generator.anthropic.Anthropic") as mock_client_cls:
            mock_client = MagicMock()
            mock_client_cls.return_value = mock_client
            mock_client.messages.create.return_value = mock_message

            generate_answer("テスト", SAMPLE_RETRIEVED)

            call_kwargs = mock_client.messages.create.call_args[1]
            assert call_kwargs["model"] == "claude-sonnet-4-6"
            assert call_kwargs["max_tokens"] == 1024
            assert call_kwargs["temperature"] == 0.3
