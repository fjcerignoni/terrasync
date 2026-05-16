# Dashboard de observabilidade — `terrasync status` (faseado)

## Context

O pipeline terrasync tem 30 sources declaradas em [apps/terrasync/sources.yaml](apps/terrasync/sources.yaml), 40+ parquets bronze materializados e 25 modelos staging, mas zero superfície de observabilidade. Hoje o usuário só sabe se uma ingestão deu certo lendo o log da execução. Conforme o catálogo cresce (SICAR cobre 27 UFs, PRODES 6 biomas, etc.), inspecionar "está fresco? quantos registros? caiu alguma fonte?" exige queries manuais.

Objetivo: painel local de saúde do pipeline, leve, sem servidor permanente, que aproveite o que já existe (footer metadata dos parquets, `runs.jsonl`, DuckDB) — e **não comprometa** o slot de `apps/api/` + `apps/web/` reservado para o futuro app React com mapa e tile server.

Este plano é **faseado**: cada fase abaixo é shippable de forma isolada. Fase 1 é pré-requisito das demais; Fases 2–5 podem ser implementadas em qualquer ordem (ou em paralelo) depois da Fase 1.

## Decisões transversais (valem para todas as fases)

- **Streamlit local**, single-page, embarcado como subcomando do CLI: `terrasync status` levanta servidor local e abre no navegador.
- **Sem API HTTP, sem Docker, sem persistência adicional.** Streamlit fala DuckDB direto e lê footer dos parquets via `pyarrow`.
- **Pasta**: `apps/terrasync/dashboard/` — acoplado ao pacote Python para reusar `config.py`, `paths.py` e `manifest.py` por import nativo.
- **Não comprometer `apps/api/` + `apps/web/`** (reservados para tile server + React/mapa).
- **DuckDB**: `duckdb.connect(":memory:")` por request com `LOAD spatial`. **Não** abrir `data/terrasync.duckdb` persistente (conflitaria com CLI rodando em paralelo).
- **Cache**: `@st.cache_data(ttl=60)` no scan de footer (barato); `ttl=3600` em validações caras. Cache key inclui `mtime` do arquivo para invalidar quando reingerir.
- **Lazy import**: dependências opcionais (`streamlit`, `httpx`) importadas dentro do handler do subcomando; mensagem clara se faltar (`uv sync --extra dashboard`).

Justificativa de descartes (curta): API agora antecipa decisões da API futura de tiles (workload completamente diferente); React/Dash custa caro pra exibir uma tabela; Docker é overhead pra app local single-user.

---

## Fase 1 — MVP: subcomando + aba Bronze health

**Entrega:** `uv run terrasync status` abre Streamlit no navegador. Aba **Visão geral** com KPIs e aba **Bronze health** com uma linha por (source, layer), semáforo de age **global** (yellow >30d, red >90d, configurável por flag — refinado por source na Fase 4).

**Por que isolada:** já responde "o que tem em bronze, há quanto tempo, tamanho, contagem". Sem cadence/probe/staging/runs.

### Arquivos a criar

- `apps/terrasync/dashboard/__init__.py` — export mínimo.
- `apps/terrasync/dashboard/app.py` — layout principal, `st.set_page_config`, abas (só Visão geral + Bronze health nesta fase), `st.sidebar` com filtro por agência usando `SOURCE_GROUPS` de [apps/terrasync/config.py](apps/terrasync/config.py).
- `apps/terrasync/dashboard/bronze.py` — `scan_bronze() -> list[dict]` itera `SOURCES`, lista `BRONZE_DIR / source.name / *.parquet`, chama `manifest.read_parquet_metadata(p)` ([apps/terrasync/manifest.py:85](apps/terrasync/manifest.py#L85)) e `Path.stat()`. Retorna `acquired_at`, `n_features`, `file_size_mb`, `endpoint`.
- `apps/terrasync/dashboard/queries.py` — wrapper `@st.cache_data(ttl=60)` em `duckdb.connect(":memory:").execute("SELECT COUNT(*) FROM read_parquet(?)")` para `actual_rows`.

### Arquivos a modificar

- `apps/terrasync/main.py`:
  - Novo `_add_status_parser(subparsers)` próximo a `_add_catalog_parser` ([apps/terrasync/main.py:51](apps/terrasync/main.py#L51)).
  - Novo `_run_status(args, logger)` com lazy import de `streamlit.web.cli` e `sys.argv = ["streamlit", "run", str(app_path), "--browser.gatherUsageStats=false"]; sys.exit(stcli.main())`.
  - Dispatch em `run()` ([apps/terrasync/main.py:178](apps/terrasync/main.py#L178)).
  - Flags: `--port` (default 8501), `--no-browser`.
- `pyproject.toml` — adicionar `[project.optional-dependencies].dashboard = ["streamlit>=1.30"]`.

### Verificação

1. `uv sync --extra dashboard`.
2. `uv run terrasync status` sobe servidor em http://localhost:8501, abre navegador.
3. Aba **Bronze health** mostra SICAR com 27 linhas (uma por UF), `acquired_at` do footer, `n_features` batendo com `actual_rows`, `file_size_mb` correto.
4. Filtro por agência na sidebar (INCRA/PRODES/DETER/SICAR/…) funciona.
5. `Ctrl+C` encerra limpo.

---

## Fase 2 — Aba Run history

**Entrega:** Aba **Run history** com últimas N entradas de `data/manifests/runs.jsonl`, filtro por status/source/layer, métricas auxiliares (duração média por strategy, taxa de falha por source).

**Por que isolada:** só lê arquivo JSONL que já existe; só adiciona aba ao app da Fase 1.

### Arquivos a criar

- `apps/terrasync/dashboard/runs.py` — `read_runs(limit=500) -> pd.DataFrame` lendo `data/manifests/runs.jsonl` com `pd.read_json(lines=True)`. Schema documentado em [apps/terrasync/manifest.py:52](apps/terrasync/manifest.py#L52).

### Arquivos a modificar

- `apps/terrasync/dashboard/app.py` — adicionar aba "Run history" com `st.dataframe` ordenado por `acquired_at` desc + filtros via `st.sidebar` ou `st.selectbox` no topo da aba.

### Verificação

1. Rodar uma ingestão (`uv run terrasync ingest <source>`).
2. Abrir aba **Run history** — última execução aparece no topo.
3. Filtrar `status=failed` mostra apenas falhas.
4. Métrica "duração média por strategy" mostra valores razoáveis para wfs/arcgis/zip.

---

## Fase 3 — Aba Staging health

**Entrega:** Aba **Staging health** com uma linha por `stg_*.parquet` em `data/staging/`, rows + file_size_mb + mtime, `n_null_geom`/`n_empty_geom`, mapeamento bronze↔staging quando 1:1, linha cinza para modelos `.sql` ainda não materializados, botão on-demand "Validar geometrias" (cacheado por mtime).

**Por que isolada:** só lê parquets de `data/staging/`; lógica independente das outras fases.

### Arquivos a modificar

- `apps/terrasync/dashboard/app.py` — adicionar aba "Staging health".
- `apps/terrasync/dashboard/queries.py` — adicionar:
  - `scan_staging() -> list[dict]` — lista `STAGING_DIR / *.parquet`, cruza com modelos `.sql` em `apps/dbt/models/staging/` para marcar "not built".
  - `geom_health(parquet_path, mtime)` cacheado: `COUNT(*) FILTER (geom IS NULL)`, `COUNT(*) FILTER (ST_IsEmpty(geom))`.
  - `validate_geometries(parquet_path, mtime)` `@st.cache_data(ttl=3600)` rodando `COUNT(*) FILTER (NOT ST_IsValid(geom))`.

### Decisões pequenas

- **Mapeamento bronze↔staging** por convenção textual: `stg_sicar.parquet` ↔ `data/bronze/sicar/*.parquet`. Funciona pra ~28 das 30 sources; resto vira "n/a" sem quebrar.
- **`st.dataframe` com `column_config.ProgressColumn`** para visualizar delta `bronze_rows → staging_rows`.

### Verificação

1. Aba **Staging health** mostra 2 linhas verdes (`stg_sicar`, `stg_ana_demanda_irrigacao`), 23 linhas cinza ("not built").
2. `n_null_geom` e `n_empty_geom` aparecem para os materializados.
3. Clicar "Validar geometrias" em `stg_sicar` retorna resultado, cacheia (segunda chamada é instantânea).

---

## Fase 4 — Cadência por source (semáforo refinado)

**Entrega:** Coluna `cadence` em `sources.yaml`, função `age_status(age_days, cadence)` pura, semáforo da aba Bronze health passa a respeitar cadência declarada (SICAR `yearly` verde até ~13 meses; DETER `daily` vermelho com 5 dias).

**Por que isolada:** apenas refina a coluna `age_status` da Fase 1. Se não rodada, semáforo continua com threshold global; se rodada, fica preciso.

### Arquivos a criar

- `apps/terrasync/dashboard/cadence.py` — `age_status(age_days: float, cadence: str) -> Literal["green","yellow","red","gray"]` puro, sem deps externas. Tabela de thresholds como dict constante:

| `cadence`   | yellow_at | red_at | uso típico |
|-------------|-----------|--------|------------|
| `daily`     | 2d        | 7d     | DETER |
| `weekly`    | 10d       | 30d    | (reserva) |
| `monthly`   | 40d       | 90d    | atualizações intermediárias |
| `quarterly` | 120d      | 270d   | (reserva) |
| `yearly`    | 400d      | 730d   | PRODES, SICAR, INCRA, IBGE |
| `unknown`   | —         | —      | cor neutra (cinza) |

### Arquivos a modificar

- `apps/terrasync/sources.yaml` — adicionar `cadence: <enum>` em cada uma das 30 sources (sem default; explicitude). ~15 minutos manuais.
- `apps/terrasync/config.py` — estender pydantic `DataSource` com `cadence: Literal["daily","weekly","monthly","quarterly","yearly","unknown"] = "unknown"`.
- `apps/terrasync/dashboard/bronze.py` — incluir `source.cadence` em `scan_bronze()`.
- `apps/terrasync/dashboard/app.py` — coluna `age` na aba Bronze health passa a colorir via `age_status()`. Granularidade por **source**, não por layer.

### Verificação

1. SICAR (yearly) com `acquired_at` de 6 meses atrás aparece verde.
2. DETER (daily) com `acquired_at` de 5 dias atrás aparece vermelho.
3. Source sem `cadence` declarado (cenário transitório) aparece cinza.
4. `uv run terrasync ingest --help` não muda (mudança é em config + dashboard).

---

## Fase 5 — Health probe de endpoints

**Entrega:** Coluna `endpoint_health` na aba Bronze health (✓ up / ⚠ slow / ✗ down / ? unknown), botão "Re-probe endpoints" no topo da aba dispara probe paralelo nas 30 sources em ~5s.

**Por que isolada:** só adiciona coluna + botão. Sem probe rodando, coluna mostra "—". Não depende de cadence nem de runs.

### Arquivos a criar

- `apps/terrasync/dashboard/probe.py`:
  - `@dataclass ProbeResult` com `status`, `http_code`, `latency_ms`, `error`, `checked_at`.
  - `async def probe(source: DataSource) -> ProbeResult` — roteia por `source.type` (wfs/arcgis/zip).
  - `async def probe_all(sources) -> dict[str, ProbeResult]` com `asyncio.gather`.

Estratégias por type:

| `type`   | probe                                                       | esperado |
|----------|-------------------------------------------------------------|----------|
| `wfs`    | `GET {base_url}?service=WFS&request=GetCapabilities`        | 200 + XML com `<WFS_Capabilities>` |
| `arcgis` | `GET {base_url}?f=json`                                     | 200 + JSON com `currentVersion`/`serviceDescription` |
| `zip`    | `HEAD {base_url}` (fallback `GET` para servers sem HEAD)    | 200/3xx em qualquer Content-Type |

Estados:
- `up` — 2xx, payload mínimo válido, latência <3s
- `slow` — 2xx mas latência ≥3s
- `down` — timeout, 4xx, 5xx, TLS/DNS error
- `unknown` — strategy sem probe (slot de fuga)

### Arquivos a modificar

- `pyproject.toml` — adicionar `httpx>=0.27` ao extra `dashboard` (já criado na Fase 1).
- `apps/terrasync/dashboard/app.py`:
  - Botão "Re-probe endpoints" no topo da aba Bronze health.
  - Resultado em `st.session_state["probe_results"]` (não `@st.cache_data` — controle manual de refresh).
  - **Sem auto-probe em todo rerender.** Probe só roda em: (1) primeira abertura (lazy, com `st.spinner`); (2) botão explícito.
  - Cada linha mostra `checked_at` para o usuário ver a idade.
- Reusar `make_ssl_context()` de [apps/terrasync/downloader/io.py:34](apps/terrasync/downloader/io.py#L34) (alguns servers federais exigem SECLEVEL=1). Passar para `httpx.AsyncClient(verify=...)`.

### Verificação

1. `uv sync --extra dashboard` (re-sync para puxar httpx).
2. Abrir dashboard — spinner "Probing endpoints…" aparece, completa em ~5s.
3. Coluna `endpoint_health` mostra mix de ✓/⚠/✗ com latências plausíveis.
4. Botão "Re-probe endpoints" reexecuta, atualiza `checked_at`.
5. Endpoint sabidamente lento (testar manualmente) volta `slow`; endpoint inexistente (mockar `base_url` inválido) volta `down`.

---

## Out of scope (deixado para v2+)

- API HTTP, autenticação, deploy remoto, multi-usuário.
- Tile serving (PostGIS → MVT) — `apps/api/` futuro.
- App React de mapa interativo — `apps/web/` futuro.
- Validação `ST_IsValid` automática em todas as fontes — só sob demanda (Fase 3).
- Integração `dbt source freshness` / `elementary` — bronze não está declarado como dbt source hoje; declarar 30 sources é trabalho próprio que extrapola este plano.
- Alertas (Slack/email) em falhas — `runs.jsonl` já dá o input pra isso quando quiser.

## Arquivos críticos para consultar na execução

- [apps/terrasync/manifest.py](apps/terrasync/manifest.py) — `read_parquet_metadata` (l. 85), `footer_metadata` (l. 33), schema do `runs.jsonl` (l. 52).
- [apps/terrasync/config.py](apps/terrasync/config.py) — `SOURCES`, `SOURCE_GROUPS`, `BRONZE_DIR`, `STAGING_DIR`, `MANIFESTS_DIR`.
- [apps/terrasync/paths.py](apps/terrasync/paths.py) — `repo_root()`, `DATA_DIR`.
- [apps/terrasync/main.py](apps/terrasync/main.py) — padrão de subparsers (l. 14-56) e dispatcher (l. 178-191).
- [apps/terrasync/downloader/io.py](apps/terrasync/downloader/io.py) — `make_ssl_context()` reutilizado pelo probe (Fase 5).
- [apps/terrasync/sources.yaml](apps/terrasync/sources.yaml) — adicionar `cadence` em cada source (Fase 4).
- [pyproject.toml](pyproject.toml) — `[project.optional-dependencies].dashboard`.