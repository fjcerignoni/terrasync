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

## Convenções

- **Naming dbt**: `stg_*` (staging/DuckDB), `canonical_*` (silver/PostGIS), `tile_*`/`analytical_*`/`mart_*` (gold/PostGIS, futuro).
- **Adicionar source nova** = editar `src/terrasync/sources.yaml` + criar `stg_*.sql` chamando `{{ clean_geometry('data/bronze/{source}/*.parquet', source_epsg=4674) }}` + criar `stg_*.yml` co-localizado. Não há código Python novo a escrever para WFS/ArcGIS/ZIP padrão.
- **`clean_geometry` aceita `relation=`** além de `parquet_path`: quando o `stg_*` precisa abrir colunas explicitamente (fonte com schema divergente, ex.: `stg_sicar`), montar um `{% set %}` com o `SELECT` e passar via `clean_geometry(relation=..., source_epsg=...)`. O gateway de staging continua único.
- **Export de cliente** = `models/exports/<cliente>/<modelo>.sql` (+ `.yml` co-localizado). Recorta o tronco compartilhado (`ref('stg_*')`) para um entregável de cliente; **não é silver**. Materializado `external`, versionado por diretório `v=YYYY-MM-DD` (dbt var `<cliente>_data_version`, default `run_started_at`).
- **Sufixo `_calc`** marca coluna gerada pelo sistema (ex.: `area_ha_calc` via `area_ha`), distinta de campo homônimo vindo da fonte.
- Pandas só no downloader (I/O heterogêneo). Em SQL, preferir DuckDB → PostGIS.

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
- **Histórico de sessões e decisões em andamento**: `ai_history.md` (ler apenas se a pergunta for sobre "por que decidimos X" ou estado de pendências).

## Após mudança arquitetônica

Atualizar `docs/architecture.md` (se afetar diagrama, escopo, decisão ou estrutura) e acrescentar sessão nova em `ai_history.md` com data, decisões e arquivos tocados.
