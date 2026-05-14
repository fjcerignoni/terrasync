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

- **Naming dbt**: `stg_*` (staging/DuckDB), `canonical_*` (silver/PostGIS, futuro), `tile_*`/`analytical_*`/`mart_*` (gold/PostGIS, futuro).
- **Adicionar source nova** = editar `src/terrasync/sources.yaml` + criar `stg_*.sql` chamando `{{ clean_geometry('data/bronze/{source}/*.parquet', source_epsg=4674) }}`. Não há código Python novo a escrever para WFS/ArcGIS/ZIP padrão.
- `SELECT *` proibido, exceto `SELECT * EXCLUDE (geometry)` em macros que propagam todas as colunas trocando a geometria.
- Pandas só no downloader (I/O heterogêneo). Em SQL, preferir DuckDB → PostGIS.

## Onde achar mais

- **Diagrama, escopo, decisões consolidadas, glossário, estrutura de pastas**: `docs/architecture.md`.
- **Design futuro silver/gold** (coverage types, tiling, templates canônicos): `docs/blueprint_geo_pipeline.md`.
- **Histórico de sessões e decisões em andamento**: `ai_history.md` (ler apenas se a pergunta for sobre "por que decidimos X" ou estado de pendências).

## Após mudança arquitetônica

Atualizar `docs/architecture.md` (se afetar diagrama, escopo, decisão ou estrutura) e acrescentar sessão nova em `ai_history.md` com data, decisões e arquivos tocados.
