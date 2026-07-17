FROM python:3.11-slim

WORKDIR /app

# 依存ライブラリのインストール
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"

# ソースコードをコピー
COPY src/ ./src/
COPY api/ ./api/
COPY data/ ./data/

# 埋め込みモデルを事前にダウンロード（ビルド時にキャッシュ）
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"

WORKDIR /app/api

EXPOSE 8000

CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
