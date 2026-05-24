# Resume work — Piloto SICAR SP+SE (canônica `layered_overlapping`)

**Última sessão:** 2026-05-13
**Plano completo:** `C:\Users\fceri\.claude\plans\1-esse-o-hidden-kite.md`
**Blueprint de referência:** [docs/blueprint_geo_pipeline.md](blueprint_geo_pipeline.md) §7.6 e §15

---

## Contexto rápido

Piloto da camada **silver** em PostGIS executando o template **§7.6
`layered_overlapping`** do blueprint (caminho mais delicado: `boundary →
ST_Node → ST_UnaryUnion → ST_Polygonize → atribuição por ST_PointOnSurface`)
restrito a **SICAR SP + SE**. Validar este template antes de escalar
porque os outros tipos de coverage são derivados mais simples.

---

## Concluído (etapas 0–4 + 7 do plano)

### Disciplina dbt formalizada
- [CLAUDE.md](../CLAUDE.md) ganhou seção `## Disciplina dbt`:
  - `schema.yml` co-localizado para todo modelo.
  - `contract.enforced: true` em silver/gold.
  - PK/FK/NOT NULL via `constraints:`; índices via `indexes:`.
  - `SELECT *` proibido em modelos finais (CTEs de passagem trivial são
    exceção; macros como `clean_geometry` mantêm `SELECT * EXCLUDE`).
  - Testes mínimos: `unique`+`not_null` em PK, `relationships` em FK.

### Configs base
- [pyproject.toml](../pyproject.toml) — `dbt-postgres>=1.8`, `psycopg2-binary>=2.9` adicionados (`uv sync` ainda **não rodado**).
- [packages.yml](../packages.yml) — novo, com `dbt-utils >=1.1, <2.0`.
- [profiles.yml](../profiles.yml) — output `postgres` adicionado, lê via `env_var('PGHOST'...)`. Output `dev` (DuckDB) preservado.
- [dbt_project.yml](../dbt_project.yml) — bloco `models.terrasync.silver` com `+materialized: table`, `+schema: silver`, `+contract.enforced: true`.

### Docker stack (criado, **não buildado** ainda)
- [infra/docker-compose.yml](../infra/docker-compose.yml) — service `postgres`, volume `pgdata`, monta `../data/staging:/data/staging:ro`. Roda de `infra/`.
- [infra/docker/postgres/Dockerfile](../infra/docker/postgres/Dockerfile) — base `postgis/postgis:16-3.5` + build de `pg_parquet 0.3.0` via `cargo-pgrx 0.12.5`. Build pesado (~10–15 min na primeira vez).
- [infra/docker/postgres/init/10-extensions.sql](../infra/docker/postgres/init/10-extensions.sql) — cria `postgis`, `postgis_topology`, `pg_parquet`, schema `silver`.
- [infra/docker/postgres/postgresql.conf](../infra/docker/postgres/postgresql.conf) — tuning piloto (`work_mem=512MB`, `maintenance_work_mem=2GB`, `shared_buffers=2GB`).
- [.env.example](../.env.example), `.gitignore` atualizado (`.env`, `pgdata/`).

### Bronze pronto
- **SICAR SP**: [data/bronze/sicar/sicar_sp.parquet](../data/bronze/sicar/sicar_sp.parquet) — 270 MB.
- **SICAR SE**: [data/bronze/sicar/sicar_se.parquet](../data/bronze/sicar/sicar_se.parquet) — 44 MB.
- **IBGE municípios 2025**: [data/bronze/ibge/ibge_municipios.parquet](../data/bronze/ibge/ibge_municipios.parquet) — 317 MB, 5.573 features (download 4.9s + parquet write 6.7s).
- Catálogo DuckDB refrescado (36 views `bronze_*`).

### Source nova registrada
- [apps/terrasync/sources.yaml](../apps/terrasync/sources.yaml) — entradas `groups.ibge` e `sources.ibge_municipios` (`zip_shapefile`, EPSG:4674).

---

## **PRÓXIMO PASSO** — começar pela Etapa 5 do plano

> Plano completo em `C:\Users\fceri\.claude\plans\1-esse-o-hidden-kite.md`,
> tabela "Etapas de execução". Etapas 0–4 + 7 já concluídas.

### Etapa 5 — Stagings DuckDB com schema.yml

1. Rodar `uv sync` para puxar `dbt-postgres` + `psycopg2-binary` (não foi feito).
2. Rodar `dbt deps` para instalar `dbt-utils`.
3. Criar [apps/dbt/models/staging/stg_ibge_municipios.sql](../apps/dbt/models/staging/stg_ibge_municipios.sql) + `.yml`:
   - Usar macro [apps/dbt/macros/clean_geometry.sql](../apps/dbt/macros/clean_geometry.sql) sobre `{{ bronze_path('ibge') }}`, `source_epsg=4674`.
   - SELECT final **explícito**: `cd_mun, nm_mun, sigla_uf, geometry`.
   - schema.yml com tests `not_null` + `unique` em `cd_mun`, `not_null` em `geometry`.
4. Criar [apps/dbt/models/staging/stg_sicar_pilot.sql](../apps/dbt/models/staging/stg_sicar_pilot.sql) + `.yml`:
   - Lê SICAR via `read_parquet('{{ bronze_path("sicar") }}', filename=true)`.
   - `regexp_extract(filename, 'sicar_(\w+)\.parquet', 1) AS uf`.
   - Filtra `WHERE uf IN ('sp','se')`.
   - Aplica `clean_geometry` (atenção: a macro hoje recebe path literal — pode ser preciso refatorar para aceitar CTE intermediária, ou inlinar a lógica de validação).
   - SELECT final explícito: `uf, cod_imovel, tipo, modulo_fiscal, municipio, situacao, geometry`.
   - Materializa em `data/staging/stg_sicar_pilot.parquet`.
5. Backfill de schema.yml para os 24 modelos `stg_*` legados (pode virar PR separado se ficar pesado, **mas a disciplina já vale a partir desta etapa**).
6. Rodar: `dbt run --select stg_sicar_pilot stg_ibge_municipios` (target `dev` = DuckDB).

### Etapas seguintes (depois de 5)

| # | Etapa | Comando-chave |
|---|---|---|
| 6 | `terrasync load --target postgres` (novo subcomando, ~150 LOC em `src/terrasync/load_postgres.py`) | `terrasync load --target postgres --source sicar_pilot ibge_municipios` |
| 7 | `grid_brasil` + `grid_pilot` (silver) | `dbt run --select grid_brasil grid_pilot --target postgres` |
| 8 | `canonical_sicar_pilot` (template §7.6) | `dbt run --select canonical_sicar_pilot --target postgres` |
| 9 | 5 testes obrigatórios em `tests/silver/` | `dbt test --select canonical_sicar_pilot --target postgres` |
| 10 | Atualizar §15 do blueprint (SP+AL → SP+SE) e métricas em `ai_history.md` | — |

### Bloqueador antes da Etapa 6
- **Subir Docker**: `docker compose up -d` — primeira vez compila pg_parquet
  (~10–15 min). Validar com `SELECT postgis_full_version()` (esperar
  `GEOS=3.14+`).

---

## Decisões fechadas (não revisitar)

1. **SP + SE** (não SP + AL como no blueprint §15 atual).
2. **Grid materializado uma vez** (`grid_brasil`); `grid_pilot` é **view**.
3. **IBGE municípios 2025** é a fonte oficial de outline para o `grid_pilot`.
4. **Postgres via Docker no repo + pg_parquet** (não ogr2ogr).
5. **Schema = `silver`**.
6. **`terrasync load --target postgres`** novo subcomando (Opção B).
7. **`canonical_sicar_pilot` materializa como `table`** no piloto, `incremental` por `tile_id` no rollout.
8. **Blueprint §15** será sobrescrito (SP+AL → SP+SE) na Etapa 10.
9. **Disciplina dbt total** (schema.yml, contracts, no `SELECT *` em modelos).

---

## Avisos para o próximo agente

- O usuário **não quer ser referenciado por nome** no plano nem nos commits.
- O usuário **prefere escrever SQL com liberdade** — por isso a disciplina dbt
  é declarativa via schema.yml, não convenção implícita.
- A macro [macros/clean_geometry.sql](../macros/clean_geometry.sql) hoje
  aceita só path literal — para `stg_sicar_pilot` (que precisa extrair `uf`
  do filename antes de validar geometria) talvez precise refatorar a macro
  ou inlinar. **Decidir na implementação.**
- `ai_history.md` é gitignored mas **deve receber sessão nova** ao final do
  piloto (data, decisões, arquivos tocados, métricas medidas).
