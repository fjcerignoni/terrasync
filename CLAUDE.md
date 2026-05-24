# terrasync

CLI Python para ingestão bulk de dados geoespaciais brasileiros (WFS/ArcGIS/ZIP shp) + staging dbt (DuckDB spatial). Arquitetura **medallion 4-tier**: bronze (parquet) → staging (DuckDB, EPSG:4326) → silver/gold (PostGIS, futuro).

Referência arquitetônica: `docs/architecture.md`.
Design futuro silver/gold: `docs/blueprint_geo_pipeline.md`.

## Invariantes geo (não-negociáveis)

- **CRS storage = EPSG:4326.** Toda geometria pós-staging está em 4326.
- **Área = EPSG:5880** (Albers BR, equal-area) via macro `area_ha(geom)`, sob demanda. Nunca calcular área em 4326 (resultado em graus²).
- **Toda geometria entra em staging pela macro `clean_geometry`**: `ST_MakeValid` + `ST_CollectionExtract(3)` + `ST_Multi` + reprojeção 4326 + bounds ±180/±90.
- **Tipo canônico pós-staging = `MULTIPOLYGON`.** Schema uniforme a jusante.
- **Bronze é imutável.** Sem particionamento temporal em snapshots geoespaciais.
- Reprojetar **uma vez** em staging. Não reprojetar dentro de joins nem em modelos a jusante.
- Layers `layered_overlapping` (CAR, SIGEF) **não** recebem `ST_CoverageClean` — sobreposições são informação, não erro.
- `ST_CoverageClean` **antes** do tiling, nunca depois.
- Preferir `ST_CoverageUnion` sobre `ST_Union` quando entrada for coverage limpa.

## Layout de pastas (monorepo)

- `apps/terrasync/` — pacote Python (ingestion engine + CLI).
- `apps/dbt/` — projeto dbt (project, profiles, models, macros, seeds, snapshots, tests, analyses). **`dbt` roda a partir de `apps/dbt/`** (cwd). O CLI in-process já passa `--project-dir`/`--profiles-dir` apontando para essa pasta.
- `apps/api/`, `apps/web/` — placeholders (futuros).
- `infra/` — `docker-compose.yml` + `docker/`. **`docker compose` roda a partir de `infra/`** (cwd).
- `data/` — fica na raiz, gitignored, compartilhado. Resolvido em runtime por `apps/terrasync/paths.py` (Python, via `repo_root()`) e por `{{ var('data_root') }}` em dbt (default `../../data`).
- `docs/`, `notebooks/`, `pyproject.toml`, `uv.lock`, `CLAUDE.md`, `README.md`, `ai_history.md` na raiz.

## Convenções

- **Naming dbt**: `stg_*` (staging/DuckDB), `canonical_*` (silver/PostGIS), `tile_*`/`analytical_*`/`mart_*` (gold/PostGIS, futuro).
- **Paths em SQL via macros**, nunca literais. Três macros centralizam o filesystem de dados:
  - `{{ bronze_path('source') }}` → `../../data/bronze/<source>/*.parquet` (aceita `glob=` para padrão custom).
  - `{{ staging_path('stg_modelo') }}` → `../../data/staging/<stg_modelo>.parquet` (usar em `location=`).
  - `{{ export_path('cliente', 'modelo') }}` → `../../data/exports/<cliente>/<modelo>/v=<YYYY-MM-DD>` (versão via `var('<cliente>_data_version')`, default `run_started_at`).
- **Adicionar fonte poligonal** → ver `docs/workflows/add_polygon_source.md`. Resumo: `sources.yaml` + `sources.yml` dbt + `stg_*.sql` + `schema.yml`. Sem código Python novo para WFS/ArcGIS/ZIP.
- **Export de cliente** → ver `docs/workflows/add_client_export.md`. Resumo: `exports/<client>/<model>.sql` + `.yml` co-localizado; recorte do staging compartilhado para entregável de cliente, **não é silver**.
- **Sufixo `_calc`** marca coluna gerada pelo sistema (ex.: `area_ha_calc` via `area_ha`), distinta de campo homônimo vindo da fonte.
- Pandas só no downloader (I/O heterogêneo). Em SQL, preferir DuckDB → PostGIS.

## Comandos

- **CLI Python**: `uv run terrasync ingest|transform|catalog ...` (de qualquer cwd — `paths.repo_root()` resolve absoluto).
- **dbt direto**: `cd apps/dbt && uv run dbt deps && uv run dbt build --select <modelo>`.
- **Docker**: `cd infra && docker compose up -d postgres`.

## Disciplina dbt (não-negociável)

- **Cada modelo tem `schema.yml` co-localizado** (mesma pasta, mesmo basename). Declara todas as colunas com `data_type`, `description`, `tests`, `constraints`.
- **`contract.enforced: true`** é padrão para silver/gold. dbt valida o DDL contra o schema declarado; mismatch falha o run.
- **PK / FK / NOT NULL** via `constraints:` no schema.yml — dbt gera o DDL no PostGIS.
- **Índices** declarados via `indexes:` na config do modelo (gist em geom, btree em FKs, gin em arrays).
- **Testes mínimos por modelo**: `unique` + `not_null` em PK; `relationships` em FK; `not_null` em colunas declaradas NOT NULL; `accepted_range`/`accepted_values` onde aplicável.
- **`SELECT *` proibido em modelos**. Listar colunas explicitamente sempre. Exceções:
  - CTE de passagem trivial (renomeação/filtro óbvio) cujo próximo passo enumera.
  - Macros que propagam colunas (`clean_geometry`) com `SELECT * EXCLUDE (...)` — mantidas pois são genéricas por design.
- **Pacote `dbt-utils`** disponível em `packages.yml` para `accepted_range`, `unique_combination_of_columns`, etc.

## Onde achar mais

- **Diagrama, escopo, decisões consolidadas, glossário, estrutura de pastas**: `docs/architecture.md`.
- **Design futuro silver/gold** (coverage types, tiling, templates canônicos): `docs/blueprint_geo_pipeline.md`.
- **Receitas de workflow** (fonte poligonal, export de cliente): `docs/workflows/`.
- **Histórico de sessões e decisões em andamento**: `ai_history.md` (ler apenas se a pergunta for sobre "por que decidimos X" ou estado de pendências).

## Em andamento

- **bdqueimadas (focos de calor)**: plano definido. Próximo passo = validar acesso WFS INPE (layer names desconhecidos). Decidir abordagem antes de implementar.
- **geometria multi-tipo**: macros separadas por tipo de vetor (`clean_geometry` polígono, `clean_point_geometry`, `clean_line_geometry`) — criar sob demanda conforme novas fontes exigirem. Raster/análise matricial no horizonte, sem prazo.

## Após mudança arquitetônica

Atualizar `docs/architecture.md` (se afetar diagrama, escopo, decisão ou estrutura) e acrescentar sessão nova em `ai_history.md` com data, decisões e arquivos tocados.
