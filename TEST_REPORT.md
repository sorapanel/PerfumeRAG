# テスト・動作確認レポート

実施日: 2026-07-05  
環境: Python 3.11.15 / ChromaDB 1.5.9 / sentence-transformers 5.6.0

---

## 1. ユニットテスト結果

```
platform darwin -- Python 3.11.15, pytest-9.1.1
15 tests collected

tests/test_generator.py::test_build_prompt_contains_query        PASSED
tests/test_generator.py::test_build_prompt_contains_document     PASSED
tests/test_generator.py::test_build_prompt_multiple_docs_separated PASSED
tests/test_generator.py::test_generate_answer_returns_string     PASSED
tests/test_generator.py::test_generate_answer_calls_correct_model PASSED
tests/test_ingest.py::test_load_json_ok                          PASSED
tests/test_ingest.py::test_load_json_not_found                   PASSED
tests/test_ingest.py::test_perfume_to_text_contains_required_fields PASSED
tests/test_ingest.py::test_build_metadata_joins_arrays           PASSED
tests/test_ingest.py::test_build_index                           PASSED
tests/test_retriever.py::test_search_returns_results             PASSED
tests/test_retriever.py::test_search_result_structure            PASSED
tests/test_retriever.py::test_search_top1_is_relevant            PASSED
tests/test_retriever.py::test_search_with_filter                 PASSED
tests/test_retriever.py::test_connection_error_on_invalid_path   PASSED

15 passed in 10.73s
```

### テスト対象と確認内容

| テストファイル | テスト数 | 確認内容 |
|---|---|---|
| `test_ingest.py` | 5 | JSON読み込み・テキスト変換・メタデータ構築・DB登録 |
| `test_retriever.py` | 5 | 類似検索・結果構造・関連性・フィルタ・接続エラー |
| `test_generator.py` | 5 | プロンプト構築・API呼び出し（モック）・モデル設定 |

---

## 2. インデックス構築

```bash
$ python scripts/build_index.py --data data/perfumes.json
```

```
インデックス構築を開始します: data/perfumes.json
1591 件の香水データをインデックスに登録しました。
インデックス構築が完了しました。
```

- データ件数: 1591件
- 埋め込みモデル: `intfloat/multilingual-e5-base`
- 永続化パス: `.chroma/`
- 重複タイトル対応: `title__brand` 形式の複合IDで吸収

---

## 3. 動作確認クエリ

### 3-1. 基本クエリ（フィルタなし）

```bash
$ python scripts/query.py "春に合う甘い香りの香水を教えてください" --top-k 3
```

**回答抜粋:**
> ## 春に合う甘い香水のご提案
>
> ### 🌸 Goutal「ローズ ポンポン（Rose Pompon）」
>
> パリの街並みを思わせる、ロマンチックで愛らしいフローラルフルーティーの香りです。
> フランボワーズのような甘酸っぱさと、豊かで愛らしいローズの香りが特徴的です。
> デートやデイリー使い、リラックスシーンにも対応できる万能さが魅力です。

---

### 3-2. シーン・スタイル指定クエリ

```bash
$ python scripts/query.py "デートに使いたいセクシーな香り" --top-k 2
```

**回答抜粋:**
> ## 🌞 Byredo｜サンデイズド（Sundazed）
>
> マンダリンやカリフォルニアンレモンの弾けるような爽やかさから始まり、
> ネロリとジャスミンの華やかさが心を高揚させます。
> コットンキャンディのような甘いムスクがふんわりと肌に残り、思わず近づきたくなるような魅力を演出します。
>
> ## 🌙 Officine Universelle Buly｜マカサー（Makassar）
>
> アイリスの気品ある残り香に、ケードやヴァージニアシダーのスモーキーな深みが重なり、
> 甘いタバコの煙のような官能的な余韻が漂います。

---

### 3-3. 季節フィルタ付きクエリ

```bash
$ python scripts/query.py "オフィス向けの清潔感のある香水" --season 春 --top-k 2
```

```
質問: オフィス向けの清潔感のある香水
フィルタ: {'season_春': {'$eq': True}}
```

**回答抜粋:**
> ## 1. 🌸 うす紅（Usubeni）／J-Scent
>
> シャンプーの残り香を思わせる、爽やかでほんのり甘いフルーティな香りが印象的です。
> ナチュラルな印象で、エレガントかつキュートな雰囲気を演出できます。
>
> ## 2. 🚿 シャワーフレッシュ（Shower Fresh）／Clean
>
> シャワー直後のような清潔感あふれるシャボンの香りが特徴です。
> フレッシュな印象で、ユニセックスに使えるシンプルさが魅力です。

---

## 4. 既知の対応事項

### ChromaDB 1.x の `$contains` 非対応

**問題:** ChromaDB 1.5.9 ではメタデータの文字列部分一致演算子 `$contains` が機能しない。

**対応:** `build_metadata` にブール型フラグを追加し、`$eq: True` で絞り込む方式に変更。

```python
# 変更前（動作しない）
where={"season": {"$contains": "春"}}

# 変更後（動作する）
where={"season_春": {"$eq": True}}
```

### 重複タイトルへの対応

**問題:** `data/perfumes.json` に同名タイトルが複数ブランドにまたがって存在（15件）。

**対応:** `ingest.py` にて2件目以降は `title__brand` 形式の複合IDを付与。

---

## 5. 使用コマンド早見表

```bash
# 仮想環境で実行する場合
PYTHONPATH=src .venv/bin/python scripts/build_index.py --data data/perfumes.json
PYTHONPATH=src .venv/bin/python scripts/query.py "質問文"
PYTHONPATH=src .venv/bin/python scripts/query.py "質問文" --top-k 3
PYTHONPATH=src .venv/bin/python scripts/query.py "質問文" --season 春
PYTHONPATH=src .venv/bin/python scripts/query.py "質問文" --scene デート
PYTHONPATH=src .venv/bin/python -m pytest tests/ -v
```
