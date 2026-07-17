# TEST_REPORT2.md — Django REST Framework API + Docker 化レポート

作成日: 2026-07-11

---

## 概要

PerfumeRAG の既存ロジック（`src/perfume_rag/`）を変更せず、その上に **Django REST Framework (DRF)** を乗せてHTTP API化した。さらに **Docker / Docker Compose** でコンテナ化し、どの環境でも同一条件で動作させられるようにした。

---

## 追加したファイル構成

```
PerfumeRAG/
├── api/                         # Django プロジェクト（新規）
│   ├── manage.py                # Django CLI エントリポイント
│   ├── config/
│   │   ├── settings.py          # 環境変数・アプリ設定
│   │   ├── urls.py              # ルートURL定義
│   │   └── wsgi.py              # gunicorn 向け WSGI アプリ
│   └── perfume_api/             # DRF アプリ本体
│       ├── serializers.py       # リクエスト/レスポンスのバリデーション
│       ├── views.py             # QueryView / HealthView
│       └── urls.py              # エンドポイント定義
├── Dockerfile                   # コンテナイメージ定義（新規）
├── docker-compose.yml           # サービス起動定義（新規）
└── pyproject.toml               # django / djangorestframework / gunicorn を追加
```

**既存の `src/perfume_rag/` には一切変更を加えていない。**

---

## エンドポイント一覧

| Method | URL | 説明 |
|---|---|---|
| `POST` | `/api/query/` | RAGクエリを実行して回答と検索ソースを返す |
| `GET` | `/api/health/` | ChromaDB の接続状態を確認する |

---

## コード解説

### 1. `api/config/settings.py` — Django 設定

```python
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR.parent / ".env")
```

`BASE_DIR` は `api/` ディレクトリを指す。`.env` はプロジェクトルートにあるため、一段上のパスを指定して読み込んでいる。

```python
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-only-insecure-key-change-in-production")
DEBUG = os.environ.get("DEBUG", "false").lower() == "true"
ALLOWED_HOSTS = os.environ.get("ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
```

すべての設定値を環境変数から取得する。ハードコードは一切していない。

```python
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "rest_framework",
    "perfume_api",
]
```

DBを使わないため `django.contrib.admin` や `django.contrib.sessions` は省略し、最小構成にしている。

```python
CHROMA_PATH = os.environ.get("CHROMA_PATH", str(BASE_DIR.parent / ".chroma"))
```

ChromaDB のパスも環境変数で差し替え可能にしており、Docker 環境ではコンテナ内のパス `/app/.chroma` を渡す。

---

### 2. `api/perfume_api/serializers.py` — バリデーション定義

DRF の `Serializer` を使ってリクエストとレスポンスの構造を明示的に定義している。

```python
class QueryRequestSerializer(serializers.Serializer):
    query   = serializers.CharField(max_length=500)
    top_k   = serializers.IntegerField(min_value=1, max_value=20, default=5)
    filters = serializers.DictField(child=serializers.CharField(), required=False, default=None)
```

- `query`: 必須、最大500文字
- `top_k`: 省略可（デフォルト5）、1〜20の範囲に制限
- `filters`: 省略可、ChromaDB の `where` 句に渡すキーバリュー辞書

```python
class SourceSerializer(serializers.Serializer):
    id       = serializers.CharField()
    document = serializers.CharField()
    metadata = serializers.DictField()
    distance = serializers.FloatField()

class QueryResponseSerializer(serializers.Serializer):
    answer  = serializers.CharField()
    sources = SourceSerializer(many=True)
    query   = serializers.CharField()
```

レスポンスは `answer`（Claudeの回答）、`sources`（検索ヒット一覧）、`query`（元の質問）の3フィールド構成。`SourceSerializer` をネストして使うことで検索結果の各フィールドも型付きで返す。

---

### 3. `api/perfume_api/views.py` — ビュー（APIの中心）

#### sys.path の操作

```python
_src_path = str(Path(settings.BASE_DIR).parent / "src")
if _src_path not in sys.path:
    sys.path.insert(0, _src_path)
```

Django プロジェクトは `api/` 以下にあり、`src/perfume_rag/` は別ディレクトリにある。Python のモジュール検索パスに `src/` を追加することで `from perfume_rag.pipeline import ask` が通るようにしている。二重追加を防ぐため `if _src_path not in sys.path` でガードしている。

#### QueryView

```python
class QueryView(APIView):
    def post(self, request: Request) -> Response:
        req_serializer = QueryRequestSerializer(data=request.data)
        if not req_serializer.is_valid():
            return Response(req_serializer.errors, status=status.HTTP_400_BAD_REQUEST)
```

まずシリアライザーでバリデーションを行う。バリデーション失敗時は `400 Bad Request` とエラー詳細を返す。

```python
        try:
            retriever = PerfumeRetriever(chroma_path=chroma_path)
            sources = retriever.search(query=query, k=top_k, filters=filters)
            answer = ask(query=query, k=top_k, filters=filters, chroma_path=chroma_path)
        except ConnectionError as e:
            return Response({"error": f"ChromaDB接続エラー: {e}"}, status=503)
        except Exception as e:
            return Response({"error": f"内部エラー: {e}"}, status=500)
```

ChromaDB への接続失敗は `ConnectionError` として区別し `503`、その他の予期しないエラーは `500` を返す。エラーを握りつぶさずHTTPステータスに変換して返すのがポイント。

#### HealthView

```python
class HealthView(APIView):
    def get(self, request: Request) -> Response:
        try:
            PerfumeRetriever(chroma_path=chroma_path)
            chroma_ok = True
        except Exception:
            pass
        payload = {"status": "ok" if chroma_ok else "degraded", "chroma": ...}
        http_status = 200 if chroma_ok else 503
```

`PerfumeRetriever` のインスタンス化を試みてChromaDBへの接続を確認する。接続できれば `200 ok`、失敗すれば `503 degraded` を返す。これによりインフラ監視ツールがAPIの死活を確認できる。

---

### 4. URLルーティング

```
リクエスト
  └─ config/urls.py:  "api/" → perfume_api.urls に委譲
       └─ perfume_api/urls.py:  "query/" → QueryView
                                "health/" → HealthView
```

Django の `include()` を使って2段階で振り分けている。アプリが増えたとき `config/urls.py` に `path("api/v2/", include(...))` を足すだけで対応できる構造。

---

## Docker 解説

### Dockerfile

```dockerfile
FROM python:3.11-slim
```

`slim` タグは不要なOSパッケージを除いた軽量版。通常の `python:3.11` より約300MB小さい。

```dockerfile
COPY pyproject.toml .
RUN pip install --no-cache-dir -e ".[dev]"
```

ソースコードより先に `pyproject.toml` だけをコピーしてインストールする。こうするとコードだけ変更した場合にこのレイヤーのキャッシュが再利用され、ビルド時間が短縮される（Dockerのレイヤーキャッシュ活用）。

```dockerfile
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('intfloat/multilingual-e5-base')"
```

埋め込みモデルをビルド時点でダウンロードしてイメージに含める。コンテナ起動時の初回遅延（数十秒〜数分）をなくすための工夫。

```dockerfile
WORKDIR /app/api
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--timeout", "120"]
```

本番WSGIサーバーとして `gunicorn` を使用。`--workers 2` は同時に2リクエストを処理できることを意味する。`--timeout 120` はClaudeのAPI呼び出しが長くかかる場合に備えたタイムアウト延長。

---

### docker-compose.yml

```yaml
services:
  api:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    environment:
      - CHROMA_PATH=/app/.chroma
      - DEBUG=false
      - ALLOWED_HOSTS=localhost,127.0.0.1
    volumes:
      - ./.chroma:/app/.chroma:ro
    restart: unless-stopped
```

| 項目 | 内容 |
|---|---|
| `env_file: .env` | `ANTHROPIC_API_KEY` をホストの `.env` から読み込む |
| `environment` | コンテナ固有の設定を上書き（`CHROMA_PATH` はコンテナ内パスを指定） |
| `volumes: ./.chroma:/app/.chroma:ro` | ホストで構築済みのインデックスをコンテナにマウント。`:ro` は読み取り専用でコンテナからの誤書き込みを防ぐ |
| `restart: unless-stopped` | クラッシュ時や再起動時に自動的にコンテナを再起動する |

---

## 動作確認結果

### GET /api/health/

```bash
curl http://localhost:8000/api/health/
```

```json
{
  "status": "ok",
  "chroma": "connected"
}
```

HTTPステータス: `200 OK`

---

### POST /api/query/

```bash
curl -X POST http://localhost:8000/api/query/ \
  -H "Content-Type: application/json" \
  -d '{"query": "春に合う甘い香りは？", "top_k": 2}'
```

```json
{
  "answer": "# 春に合う甘い香りのご提案\n\n...(Claudeの回答)...",
  "sources": [
    {
      "id": "Glicine",
      "document": "名前: グリシン（Glicine）\nブランド: Acca Kappa\n...",
      "metadata": { "brand": "Acca Kappa", "season": "春,夏,秋,冬", ... },
      "distance": 0.176
    },
    ...
  ],
  "query": "春に合う甘い香りは？"
}
```

HTTPステータス: `200 OK`

---

## 起動コマンドまとめ

```bash
# 開発サーバーで起動（ローカル確認用）
.venv/bin/python api/manage.py runserver 8000

# Docker でビルド＆起動
docker compose up --build

# バックグラウンドで起動
docker compose up --build -d

# ログ確認
docker compose logs -f

# 停止
docker compose down
```

---

## 今後の拡張ポイント

| 課題 | 対応案 |
|---|---|
| 本番デプロイ | `DJANGO_SECRET_KEY` を強力なランダム値に変更、`ALLOWED_HOSTS` に本番ドメインを追加 |
| 認証 | DRF の `TokenAuthentication` または `SessionAuthentication` を追加 |
| レートリミット | `django-ratelimit` でエンドポイントごとにリクエスト数を制限 |
| ログ | Django の `LOGGING` 設定で構造化ログ（JSON形式）を出力 |
| テスト | `pytest-django` で `QueryView` / `HealthView` の単体テストを追加 |
