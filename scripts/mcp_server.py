"""香水RAGの検索（Retrieval）のみをMCPツールとして公開するサーバー。

生成（Generation）は行わない。呼び出し側のClaude（Claude Desktop / Claude Code等）が
このツールで取得した検索結果をもとに自分で回答を生成する構成。

起動方法:
    # ローカルでClaude Codeにstdio接続する場合
    .venv/bin/python scripts/mcp_server.py

    # リモート公開する場合（例: Fly.io）
    # TLS終端はプラットフォーム側（Fly.io等）が担当する前提。
    # 以下は必須の環境変数:
    #   MCP_TRANSPORT=streamable-http
    #   MCP_AUTH_TOKEN=<ランダムな共有シークレット>       … 未設定なら起動時にエラーで落ちる
    #   MCP_ALLOWED_HOSTS=your-app.fly.dev              … DNS rebinding対策。未設定なら起動時にエラーで落ちる
    MCP_TRANSPORT=streamable-http MCP_AUTH_TOKEN=xxx MCP_ALLOWED_HOSTS=your-app.fly.dev \
        .venv/bin/python scripts/mcp_server.py
"""

import hmac
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mcp.server.mcpserver import MCPServer

from perfume_rag.retriever import DEFAULT_TOP_K, PerfumeRetriever

CHROMA_PATH = os.getenv("CHROMA_PATH", ".chroma")

mcp = MCPServer(
    name="perfume-search",
    instructions=(
        "香水データベースを意味検索するツール。ユーザーの好み・シーン・季節に合う"
        "香水を探すときに使う。検索結果の document を根拠として回答を生成すること。"
    ),
)

_retriever: PerfumeRetriever | None = None


def _get_retriever() -> PerfumeRetriever:
    global _retriever
    if _retriever is None:
        _retriever = PerfumeRetriever(chroma_path=CHROMA_PATH)
    return _retriever


def _build_filters(season: str | None, scene: str | None) -> dict | None:
    conditions = []
    if season:
        conditions.append({f"season_{season}": {"$eq": True}})
    if scene:
        conditions.append({f"scene_{scene}": {"$eq": True}})

    if not conditions:
        return None
    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


@mcp.tool()
def search_perfumes(
    query: str,
    top_k: int = DEFAULT_TOP_K,
    season: str | None = None,
    scene: str | None = None,
) -> list[dict]:
    """自然言語クエリに意味的に類似した香水を検索する。

    Args:
        query: 検索したい香水の特徴（例: "春に合う甘い香り"）
        top_k: 取得件数
        season: 季節フィルタ（春/夏/秋/冬のいずれか）
        scene: シーンフィルタ（例: デート、オフィス）

    Returns:
        [{"id": str, "document": str, "metadata": dict, "distance": float}, ...]
    """
    filters = _build_filters(season, scene)
    return _get_retriever().search(query=query, k=top_k, filters=filters)


class _BearerAuthMiddleware:
    """Authorization: Bearer <token> を検証するASGIミドルウェア。

    streamable-http でリモート公開する際、誰でも呼べる状態を防ぐための
    最低限のゲート。MCP SDK標準のOAuth機構（AuthSettings）は外部の認可サーバーを
    前提とするため、個人利用の共有トークン方式には過剰と判断しここでは使わない。
    """

    def __init__(self, app, token: str) -> None:
        self._app = app
        self._token = token

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        # Fly.ioのヘルスチェックは "/" にAuthorizationヘッダー無しでアクセスしてくる。
        # ここを認証対象にすると常に401になり、Flyがマシンを健全と判断できず実トラフィックが
        # 一切回ってこなくなる（"/mcp" は検索ツール本体なので当然認証対象のまま）。
        if scope["path"] == "/":
            from starlette.responses import PlainTextResponse

            response = PlainTextResponse("ok", status_code=200)
            await response(scope, receive, send)
            return

        headers = dict(scope.get("headers") or [])
        raw = headers.get(b"authorization", b"").decode("latin-1")
        provided = raw.removeprefix("Bearer ").strip()

        # hmac.compare_digest でタイミング攻撃によるトークン推測を防ぐ
        if not provided or not hmac.compare_digest(provided, self._token):
            from starlette.responses import PlainTextResponse

            response = PlainTextResponse("Unauthorized", status_code=401)
            await response(scope, receive, send)
            return

        await self._app(scope, receive, send)


def _run_remote() -> None:
    """streamable-http でリモート公開する（Fly.io等、TLS終端は外側に任せる前提）。"""
    import uvicorn
    from mcp.server.transport_security import TransportSecuritySettings

    # フェイルクローズ: 認証トークンとHost許可リストが無いまま公開されるのを防ぐ
    auth_token = os.environ["MCP_AUTH_TOKEN"]

    allowed_hosts = [h for h in os.environ["MCP_ALLOWED_HOSTS"].split(",") if h]
    allowed_origins = [o for o in os.getenv("MCP_ALLOWED_ORIGINS", "").split(",") if o]

    app = mcp.streamable_http_app(
        host="0.0.0.0",
        transport_security=TransportSecuritySettings(
            enable_dns_rebinding_protection=True,
            allowed_hosts=allowed_hosts,
            # ブラウザ経由のクライアントは想定しないため、明示指定が無ければ全拒否のまま
            allowed_origins=allowed_origins,
        ),
    )
    app = _BearerAuthMiddleware(app, token=auth_token)

    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "8080")))


if __name__ == "__main__":
    transport = os.getenv("MCP_TRANSPORT", "stdio")
    if transport == "stdio":
        _get_retriever()  # ローカル用途では起動時に済ませて最初のリクエストのレイテンシを避ける
        mcp.run(transport="stdio")
    elif transport == "streamable-http":
        # ここでは事前ロードしない: モデルロード時間がそのままヘルスチェックの
        # 合否に直結してしまう（Fly.ioのgrace_periodは最大60秒）ため、
        # ポートは即座に開けて、モデルロードは最初の検索リクエスト時まで遅延させる。
        _run_remote()
    else:
        raise ValueError(f"Unknown MCP_TRANSPORT: {transport}")
