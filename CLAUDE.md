# CLAUDE.md — perfumeRAG プロジェクト作業指示

## プロジェクト概要

香水JSONデータを用いたRAGシステム。詳細は `SPEC.md` を参照。

---

## 作業前に必ず確認すること

1. `SPEC.md` を読み、仕様を把握する
2. `.env` に `ANTHROPIC_API_KEY` が設定されているか確認する
3. 依存ライブラリがインストール済みか確認する（`pip list | grep chromadb`）

---

## ディレクトリ構成の原則

- **ロジックは `src/perfume_rag/` に置く**（ingest / retriever / generator / pipeline）
- **実行スクリプトは `scripts/` に置く**（ロジックをimportして使うだけ）
- **テストは `tests/` に置く**
- **データは `data/` に置く**（コードと混在させない）

---

## コーディング規約

### 言語・スタイル

- Python 3.11+
- 型ヒントを必ず付ける（`def func(x: str) -> list[str]:` 形式）
- docstring は Google スタイル（日本語で書いてよい）
- 1ファイル = 1責務（ingest はインデックス構築のみ、retriever は検索のみ）

### 命名規則

```python
# 関数: snake_case
def load_perfume_data(path: str) -> list[dict]: ...

# クラス: PascalCase
class PerfumeRetriever: ...

# 定数: UPPER_SNAKE_CASE
DEFAULT_TOP_K = 5
COLLECTION_NAME = "perfumes"
```

### エラーハンドリング

- ファイルが存在しない場合は `FileNotFoundError` を raise（握りつぶさない）
- APIエラーは上位に伝播させる（スクリプト側でキャッチしてメッセージ表示）
- ChromaDB接続エラーは `ConnectionError` にラップして raise

---

## 各モジュールの責務

### `src/perfume_rag/ingest.py`

```
役割: JSONを読み込み、テキスト変換してChromaDBに登録する

主要関数:
  - load_json(path: str) -> list[dict]
  - perfume_to_text(perfume: dict) -> str   # SPEC.md のテンプレートに従う
  - build_metadata(perfume: dict) -> dict
  - build_index(json_path: str, chroma_path: str) -> None
```

### `src/perfume_rag/retriever.py`

```
役割: ChromaDBに接続し、クエリに類似した香水を返す

主要クラス/関数:
  - class PerfumeRetriever
      - __init__(chroma_path: str)
      - search(query: str, k: int, filters: dict | None) -> list[dict]
        返り値: [{"id": str, "document": str, "metadata": dict, "distance": float}]
```

### `src/perfume_rag/generator.py`

```
役割: 検索結果とクエリをClaude APIに渡して回答を生成する

主要関数:
  - build_prompt(query: str, retrieved: list[dict]) -> str
  - generate_answer(query: str, retrieved: list[dict]) -> str
```

### `src/perfume_rag/pipeline.py`

```
役割: retriever + generator を組み合わせたエンドツーエンドの処理

主要関数:
  - ask(query: str, k: int, filters: dict | None) -> str
```

---

## よく使うコマンド

```bash
# 依存ライブラリのインストール
pip install -e ".[dev]"

# インデックス構築（データ変更時に再実行）
python scripts/build_index.py --data data/perfumes.json

# 質問を投げる
python scripts/query.py "春に合う甘い香りは？"
python scripts/query.py "デートに使いたい" --top-k 3

# テスト実行
pytest tests/ -v

# 特定モジュールのテストのみ
pytest tests/test_retriever.py -v
```

---

## 実装順序（推奨）

1. `pyproject.toml` と `.env.example` を作成
2. `src/perfume_rag/ingest.py` を実装・テスト
3. `scripts/build_index.py` を実装してインデックス構築を確認
4. `src/perfume_rag/retriever.py` を実装・テスト
5. `src/perfume_rag/generator.py` を実装・テスト
6. `src/perfume_rag/pipeline.py` で統合
7. `scripts/query.py` で動作確認

---

## 禁止事項

- `src/` 以下にAPIキーをハードコードしない（必ず環境変数から読む）
- `data/perfumes.json` をコードにハードコードしない（引数 or 環境変数で渡す）
- ChromaDB の `.chroma/` ディレクトリをGitにコミットしない
- `ingest.py` に検索ロジックを書かない（責務分離）

---

## トラブルシューティング

### インデックスが空/見つからない
```bash
# .chroma/ ディレクトリを確認
ls -la .chroma/
# 再構築
python scripts/build_index.py --data data/perfumes.json
```

### 埋め込みモデルのダウンロードが遅い
`sentence-transformers` は初回起動時にモデルをダウンロードする。
`~/.cache/huggingface/` にキャッシュされるので2回目以降は高速。

### ChromaDB のバージョンエラー
```bash
pip install --upgrade chromadb
```

### APIキーエラー
```bash
# .env を確認
cat .env
# export で直接設定する場合
export ANTHROPIC_API_KEY=sk-ant-...
```
