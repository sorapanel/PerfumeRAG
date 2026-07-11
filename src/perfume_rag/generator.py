"""検索結果とクエリをClaude APIに渡して回答を生成するモジュール。"""

import os

import anthropic
from dotenv import load_dotenv

load_dotenv()

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024
TEMPERATURE = 0.3

SYSTEM_PROMPT = """あなたは香水のエキスパートアドバイザーです。
以下の香水情報を参考に、ユーザーの質問に日本語で丁寧に回答してください。
複数の香水が該当する場合は、それぞれの特徴を比較しながら紹介してください。"""

GUIDELINES = """【回答のガイドライン】
- ブランド名と香水名を必ず明記する
- 香りの特徴をわかりやすい言葉で説明する
- シーンや季節への適性を具体的に述べる
- 参考情報にない内容は推測で答えない"""


def build_prompt(query: str, retrieved: list[dict]) -> str:
    """検索結果とクエリからClaudeへ渡すプロンプトを構築する。

    Args:
        query: ユーザーの質問
        retrieved: retriever.search()の返り値

    Returns:
        完成したプロンプト文字列
    """
    docs_text = "\n---\n".join(item["document"] for item in retrieved)
    return (
        f"【参考にする香水情報】\n{docs_text}\n\n"
        f"【ユーザーの質問】\n{query}\n\n"
        f"{GUIDELINES}"
    )


def generate_answer(query: str, retrieved: list[dict]) -> str:
    """Claude APIを呼び出して回答を生成する。

    Args:
        query: ユーザーの質問
        retrieved: retriever.search()の返り値

    Returns:
        Claudeが生成した回答文字列

    Raises:
        anthropic.APIError: Claude APIの呼び出しに失敗した場合
    """
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    prompt = build_prompt(query, retrieved)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text
