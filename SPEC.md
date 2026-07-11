# perfumeRAG 仕様書

## 概要

香水JSONデータを対象とした RAG（Retrieval-Augmented Generation）システム。
ユーザーが自然言語で香水の特徴・シーン・気分を入力すると、関連する香水を検索し、Claude が自然な文章で回答を生成する。

---

## ディレクトリ構成

```
~/Workplace/perfumeRAG/
├── SPEC.md               # 本仕様書
├── CLAUDE.md             # Claude Code 向け作業指示
├── README.md             # セットアップ手順
├── pyproject.toml        # 依存関係 (uv 管理)
├── data/
│   └── perfumes.json     # 元データ（香水マスターデータ）
├── src/
│   └── perfume_rag/
│       ├── __init__.py
│       ├── ingest.py     # JSONを読み込み、ベクトルDBへ登録
│       ├── retriever.py  # 類似検索ロジック
│       ├── generator.py  # Claude APIでの回答生成
│       └── pipeline.py   # ingest → retrieve → generate をまとめたエントリポイント
├── scripts/
│   ├── build_index.py    # インデックス構築スクリプト（1回だけ実行）
│   └── query.py          # CLIから質問するスクリプト
├── tests/
│   ├── test_ingest.py
│   ├── test_retriever.py
│   └── test_generator.py
└── .chroma/              # ChromaDB の永続化ディレクトリ（gitignore対象）
```

---

## データ仕様

### 入力データ: `data/perfumes.json`

```json
[
  {
    "title": "Lazy Sunday Morning",
    "titleJp": "レイジー サンデー モーニング",
    "brand": "Maison Margiela",
    "concept": "...",
    "top": ["アルデヒド", "スズラン", "ペアー"],
    "middle": ["ローズ", "アイリス", "オレンジブロッサム"],
    "last": ["ムスク", "アンブレット", "パチュリ"],
    "imagery": ["エレガント", "セクシー", "ベーシック"],
    "impression": ["ナチュラル"],
    "scenes": ["オフィス", "デート", "デイリー", "パーティー", "リラックス"],
    "season": ["春", "夏", "秋"]
  }
]
```

### フィールド定義

| フィールド  | 型       | 説明                                 |
|------------|----------|--------------------------------------|
| title      | string   | 香水の英語名（ユニークID として使用）|
| titleJp    | string   | 香水の日本語名                       |
| brand      | string   | ブランド名                           |
| concept    | string   | コンセプト文（検索精度に最も影響）   |
| top        | string[] | トップノート                         |
| middle     | string[] | ミドルノート                         |
| last       | string[] | ラストノート                         |
| imagery    | string[] | イメージタグ                         |
| impression | string[] | 印象タグ                             |
| scenes     | string[] | シーンタグ                           |
| season     | string[] | 季節タグ                             |

---

## テキスト変換仕様（チャンク設計）

1香水 = 1ドキュメント。以下のテンプレートで結合する。

```
名前: {titleJp}（{title}）
ブランド: {brand}
コンセプト: {concept}
トップノート: {top をカンマ区切り}
ミドルノート: {middle をカンマ区切り}
ラストノート: {last をカンマ区切り}
イメージ: {imagery をカンマ区切り}
印象: {impression をカンマ区切り}
シーン: {scenes をカンマ区切り}
季節: {season をカンマ区切り}
```

---

## ベクトルDB 仕様

| 項目             | 内容                                         |
|-----------------|----------------------------------------------|
| ライブラリ       | ChromaDB（ローカル永続化）                   |
| 埋め込みモデル   | `intfloat/multilingual-e5-base`（日本語対応）|
| コレクション名   | `perfumes`                                   |
| ドキュメントID   | `title`（英語名）                            |
| 永続化パス       | `.chroma/`                                   |
| メタデータ       | brand, season, scenes, imagery, impression   |

### メタデータ登録例

```python
metadata = {
    "brand": "Maison Margiela",
    "season": "春,夏,秋",      # カンマ区切り文字列
    "scenes": "オフィス,デート",
    "imagery": "エレガント,セクシー",
    "impression": "ナチュラル",
}
```

---

## 検索仕様（Retrieval）

- デフォルト取得件数: `k=5`
- 類似度: コサイン類似度（ChromaDB デフォルト）
- メタデータフィルタ: オプション（season / scenes での絞り込みに対応）

### フィルタ例

```python
collection.query(
    query_texts=["甘くてフローラルな香り"],
    n_results=5,
    where={"season": {"$contains": "春"}}  # 春限定
)
```

---

## 回答生成仕様（Generation）

### 使用モデル

`claude-sonnet-4-6`

### プロンプト構造

```
あなたは香水のエキスパートアドバイザーです。
以下の香水情報を参考に、ユーザーの質問に日本語で丁寧に回答してください。
複数の香水が該当する場合は、それぞれの特徴を比較しながら紹介してください。

【参考にする香水情報】
{retrieved_documents を --- で区切って結合}

【ユーザーの質問】
{user_question}

【回答のガイドライン】
- ブランド名と香水名を必ず明記する
- 香りの特徴をわかりやすい言葉で説明する
- シーンや季節への適性を具体的に述べる
- 参考情報にない内容は推測で答えない
```

### APIパラメータ

| パラメータ  | 値     |
|------------|--------|
| model      | claude-sonnet-4-6 |
| max_tokens | 1024   |
| temperature| 0.3（再現性重視） |

---

## CLI インターフェース

### インデックス構築

```bash
python scripts/build_index.py --data data/perfumes.json
```

### クエリ実行

```bash
python scripts/query.py "春に合う甘い香りの香水を教えてください"
python scripts/query.py "デートに使えるセクシーな香りは？" --top-k 3
python scripts/query.py "オフィス向けの香水" --season 春 --top-k 5
```

---

## 環境変数

| 変数名              | 説明                        |
|--------------------|-----------------------------|
| ANTHROPIC_API_KEY  | Claude API キー（必須）      |
| CHROMA_PATH        | DBパス（デフォルト: .chroma）|
| EMBED_MODEL        | 埋め込みモデル名（変更可）   |

---

## 依存ライブラリ

```toml
[project]
name = "perfume-rag"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "anthropic>=0.25.0",
    "chromadb>=0.5.0",
    "sentence-transformers>=3.0.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]
```

---

## テスト方針

| テスト対象       | 確認内容                                         |
|----------------|--------------------------------------------------|
| ingest.py      | JSON読み込み → テキスト変換 → DB登録が正常に完了する |
| retriever.py   | クエリに対して上位k件が返される。IDが正しい       |
| generator.py   | Claude APIから文字列が返される（モック推奨）     |

---

## 制約・注意事項

- `data/perfumes.json` はユーザーが用意する（リポジトリには含めない）
- APIキーは `.env` で管理し、`.gitignore` に追加する
- ChromaDB の `.chroma/` ディレクトリも `.gitignore` 対象
- 埋め込みモデルの初回ダウンロードに数分かかる場合がある
