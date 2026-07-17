"""perfumeRAG API ビュー。"""

import sys
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

# src/ を sys.path に追加（Djangoアプリから perfume_rag を import するため）
_src_path = str(Path(settings.BASE_DIR).parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)

from perfume_rag.pipeline import ask  # noqa: E402
from perfume_rag.retriever import PerfumeRetriever  # noqa: E402

from .serializers import QueryRequestSerializer, QueryResponseSerializer  # noqa: E402


class QueryView(APIView):
    """POST /api/query/ — 香水RAGクエリを実行して回答を返す。"""

    def post(self, request: Request) -> Response:
        req_serializer = QueryRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        query: str = req_serializer.validated_data["query"]
        top_k: int = req_serializer.validated_data["top_k"]
        filters: dict | None = req_serializer.validated_data.get("filters")

        chroma_path = settings.CHROMA_PATH

        try:
            retriever = PerfumeRetriever(chroma_path=chroma_path)
            sources = retriever.search(query=query, k=top_k, filters=filters)
            answer = ask(
                query=query,
                k=top_k,
                filters=filters,
                chroma_path=chroma_path,
            )
        except ConnectionError as e:
            return Response(
                {"error": f"ChromaDB接続エラー: {e}"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            return Response(
                {"error": f"内部エラー: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        res_serializer = QueryResponseSerializer(
            {"answer": answer, "sources": sources, "query": query}
        )
        return Response(res_serializer.data, status=status.HTTP_200_OK)


class HealthView(APIView):
    """GET /api/health/ — サービスの稼働状態を確認する。"""

    def get(self, request: Request) -> Response:
        chroma_path = settings.CHROMA_PATH
        chroma_ok = False
        try:
            PerfumeRetriever(chroma_path=chroma_path)
            chroma_ok = True
        except Exception:
            pass

        payload = {
            "status": "ok" if chroma_ok else "degraded",
            "chroma": "connected" if chroma_ok else "unavailable",
        }
        http_status = status.HTTP_200_OK if chroma_ok else status.HTTP_503_SERVICE_UNAVAILABLE
        return Response(payload, status=http_status)
