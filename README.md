# 🛰️ Geo Flood Agent — Daytona × Nosana × Neo4j

**「荒川下流で水位が3m上がったら、浸水範囲と影響を受ける施設は？」** と聞くと、

1. **Nosana** 上の LLM（分散GPU・OpenAI互換）が GIS 処理の Python スクリプトを書き
2. **Daytona** の使い捨てサンドボックスがそれを隔離実行（国土地理院の実標高タイルを取得 → 浸水マスク → 地図PNG）
3. **Neo4j** に浸水シナリオを書き込み、**「浸水していないのに、給電元の変電所が浸水して停電する施設」** を多段クエリで返す
4. Nosana の LLM が EOC 向けの日本語ブリーフィングを生成

UI はイベントを SSE でストリームし、各ステップにどのスポンサープラットフォームが動いているかタグ表示します。

## セットアップ（5分）

```bash
cd geo-agent
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env      # キーを3つ貼る（下記）
python smoke.py           # 各プラットフォームに hello world を1回ずつ通す（〜60秒）
uvicorn app:app --port 8000
open http://localhost:8000
```

### 必要なキー（.env）

| Platform | 値 | 取得場所 |
|---|---|---|
| Nosana | `NOSANA_BASE_URL=https://<job-id>.node.k8s.prd.nos.ci/v1` | ダッシュボードで vLLM/Ollama テンプレートをデプロイ → Service URL。`NOSANA_MODEL` は空なら `/v1/models` から自動検出 |
| Daytona | `DAYTONA_API_KEY` | app.daytona.io → API Keys |
| Neo4j | `NEO4J_URI`, `NEO4J_PASSWORD` | console.neo4j.io → Free instance（作成時に表示されるパスワード） |

**キーが無い／死んでいるプラットフォームは自動でモックにフォールバック**します（`USE_NOSANA=0` 等で強制もできる）。
モック時はUIのバッジが `mock` 表示になり、デモは止まりません。

### Daytona の起動を速くする（任意・1回だけ）

```bash
python -m agent.sandbox            # numpy/matplotlib 入りスナップショット geo-agent-py312 をビルド
echo DAYTONA_SNAPSHOT=geo-agent-py312 >> .env
```
未設定でも `Image.debian_slim().pip_install()` で宣言的にビルドされ、2回目以降はキャッシュされます。
**smoke.py か1回目の実行をデモ前に必ず通しておく**こと（初回ビルドをキャッシュさせるため）。

## 構成

```
app.py                 FastAPI + SSE
static/index.html      デモUI（プラットフォーム別タグのライブログ、地図、施設表、波及表、生成コード、Cypher）
agent/pipeline.py      オーケストレーション（イベントを yield）
agent/llm.py           Nosana(OpenAI互換) → OpenAI → Anthropic → 定型スクリプト の順にフォールバック
agent/sandbox.py       Daytona で upload → exec → download → delete。失敗時はローカル subprocess
agent/graph.py         Neo4j（seed / シナリオ書込 / 波及Cypher）。失敗時はインメモリ同等実装
agent/seed_data.py     サンプル施設グラフ（変電所・病院・避難所、POWERED_BY / BACKUP_OF）※架空データ
sandbox_lib/geo_helpers.py  サンドボックス内で動く GIS ヘルパー（GSI 標高タイル取得・浸水マスク・描画）
smoke.py               3プラットフォームの疎通テスト
```

## データについて
- 標高: 国土地理院 標高タイル（DEM10B, `cyberjapandata.gsi.go.jp/xyz/dem_png`）を実行時に取得。取得不能時は合成DEM（`SYNTHETIC` と明示）。
- 施設・給電関係: **デモ用の架空サンプル**（名称に `(sample)` 付き）。実データに差し替える場合は `seed_data.py` か Neo4j を直接編集。
- 浸水モデルは bathtub（標高 ≤ 水位）。デモ用の簡易モデルであり、ハザードマップの代替ではありません。

## 波及クエリ（Neo4j が必要な理由）

```cypher
MATCH (f:Facility)-[:POWERED_BY]->(sub:Facility)-[fl:FLOODED_IN]->(s:Scenario {id:$sid})
WHERE NOT (f)-[:FLOODED_IN]->(s)
OPTIONAL MATCH (bk:Facility)-[:BACKUP_OF]->(sub)
RETURN f.name, sub.name AS via, fl.depth_m, bk.name AS backup
```
「水に浸かっていないのに機能停止する施設」はラスタ解析だけでは出ない。関係を辿って初めて分かる。
