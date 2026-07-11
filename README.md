# perfumeRAG

香水データを対象とした RAG（Retrieval-Augmented Generation）システム。  
自然言語で香水の雰囲気やシーンを入力すると、1591件の香水データから関連する香水を検索して Claude が提案します。

---

## 技術スタック

| 役割 | ライブラリ / サービス |
|---|---|
| ベクトルDB | ChromaDB（ローカル永続化） |
| 埋め込みモデル | intfloat/multilingual-e5-base |
| LLM | Claude (claude-sonnet-4-6) |
| 言語 | Python 3.11+ |

---

## セットアップ

### 1. リポジトリのクローン

```bash
git clone https://github.com/<your-username>/perfumeRAG.git
cd perfumeRAG
```

### 2. Python 3.11 仮想環境の作成

```bash
# uv を使う場合（推奨）
pip install uv
python3 -m uv venv --python 3.11 .venv

# 依存ライブラリのインストール
python3 -m uv pip install --python .venv/bin/python -e ".[dev]"
```

### 3. 環境変数の設定

```bash
cp .env.example .env
# .env を開いて ANTHROPIC_API_KEY を設定する
```

`.env` の内容:

```
ANTHROPIC_API_KEY=sk-ant-...
CHROMA_PATH=.chroma
EMBED_MODEL=intfloat/multilingual-e5-base
```

> APIキーは [Anthropic Console](https://console.anthropic.com/) で取得できます。

### 4. 香水データを配置

```bash
cp /path/to/your/perfumes.json data/perfumes.json
```

`data/perfumes.json` はリポジトリに含まれていません。ご自身で用意してください（フォーマットは `SPEC.md` 参照）。

### 5. インデックス構築

```bash
PYTHONPATH=src .venv/bin/python scripts/build_index.py --data data/perfumes.json
```

初回はモデルのダウンロードに数分かかります。

---

## 使い方

```bash
# 基本的な質問
PYTHONPATH=src .venv/bin/python scripts/query.py "春に合う甘い香りの香水を教えてください"

# 件数を指定
PYTHONPATH=src .venv/bin/python scripts/query.py "デートに使いたいセクシーな香り" --top-k 3

# 季節で絞り込み
PYTHONPATH=src .venv/bin/python scripts/query.py "オフィスで使える清潔感のある香水" --season 春

# シーンで絞り込み
PYTHONPATH=src .venv/bin/python scripts/query.py "リラックスできる香り" --scene リラックス

# 季節とシーンを組み合わせ
PYTHONPATH=src .venv/bin/python scripts/query.py "爽やかな香水" --season 夏 --scene デート
```

---

## テスト

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v
```

---

## ディレクトリ構成

```
perfumeRAG/
├── data/
│   └── perfumes.json        # 香水マスターデータ（要配置・gitignore対象）
├── src/perfume_rag/
│   ├── ingest.py            # JSONを読み込みChromaDBに登録
│   ├── retriever.py         # 類似検索ロジック
│   ├── generator.py         # Claude APIで回答生成
│   └── pipeline.py          # エンドツーエンド処理
├── scripts/
│   ├── build_index.py       # インデックス構築スクリプト
│   └── query.py             # CLIクエリスクリプト
├── tests/                   # ユニットテスト
├── .env.example             # 環境変数テンプレート
├── pyproject.toml           # 依存関係定義
├── SPEC.md                  # システム仕様書
└── TEST_REPORT.md           # テスト・動作確認レポート
```

---

## ドキュメント

| ファイル | 内容 |
|---|---|
| `SPEC.md` | システム仕様（データ形式・API設計・テスト方針） |
| `TEST_REPORT.md` | テスト結果・動作確認ログ |
