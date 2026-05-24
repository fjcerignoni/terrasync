# Blueprint — Pipeline Geoespacial Multi-Layer

**Escopo:** geoprocessamento de N layers vetoriais sobre o território brasileiro com PostGIS, dbt-core (DuckDB + Postgres) e Python como orquestrador.
**Não inclui:** aquisição de dados, visualização, API de consulta.

---

## 1. Pré-requisitos de versão

A família `ST_Coverage*` é o core deste blueprint. Versões mínimas obrigatórias:

| Componente | Versão mínima | Por quê |
|---|---|---|
| PostgreSQL | 14+ | Performance de window functions e parallel workers |
| PostGIS | **3.6+** | Suporte completo a `ST_CoverageClean` |
| GEOS | **3.14+** | `ST_CoverageClean` (3.14), `ST_CoverageSimplify` (3.12), `ST_CoverageInvalidEdges` (3.12), `ST_CoverageUnion` (3.12) |
| dbt-core | 1.7+ | Adapter unions, `on_schema_change`, modelos materialized |
| dbt-postgres | 1.7+ | — |
| dbt-duckdb | 1.7+ | — |
| DuckDB | 0.10+ | Spatial extension estável |

**Validação imediata após instalar:**
```sql
SELECT postgis_full_version();
-- Procurar "GEOS=3.14" ou superior. Se for 3.12 ou 3.13, ST_CoverageClean não está disponível
-- e partes do pipeline precisam de fallback (ver seção 8).
```

---

## 2. Princípios da arquitetura

| Princípio | Implicação |
|---|---|
| **Cobertura total** | Cada fragmento existe com ou sem sobreposição. NULL é valor válido em qualquer coluna de ID. |
| **Coverage-first** | Toda layer é tratada como coverage potencial. `ST_CoverageInvalidEdges` é o teste de qualidade primário. |
| **Modularidade por layer** | Cada layer produz uma forma canônica independente. Adicionar layer N+1 não exige alterar nada já feito. |
| **Particionamento espacial fixo** | Grid de referência único recorta todas as layers. Tile é unidade de paralelismo. |
| **Adapter por custo** | DuckDB para parquet/staging. PostGIS para topologia (coverage operations). |
| **Idempotência** | Reprocessar layer/tile não corrompe o resto. `unique_key` em modelos incrementais. |
| **Auditoria** | `source_ids[]` em cada fragmento canônico rastreia origem. |

---

## 3. Conceito central: Coverage vs Non-Coverage

A família `ST_Coverage*` opera sobre **coverages poligonais** — conjuntos de polígonos que:

1. **Não se sobrepõem** (interiores disjuntos)
2. **Têm edges idênticos** nas fronteiras compartilhadas (vertex-to-vertex matching)

Layers do mundo real raramente chegam nessa condição. A estratégia é **classificar cada layer e tratar conforme o caso**:

| Categoria | Característica | Exemplos | Tratamento |
|---|---|---|---|
| **Native coverage** | Já é coverage limpa na origem | Municípios IBGE, UFs, biomas | `ST_CoverageInvalidEdges` para verificar; se passar, prossegue direto |
| **Dirty coverage** | Pretende ser coverage mas tem gaps/overlaps mínimos por imprecisão | TI FUNAI, UC ICMBio, malha fundiária estadual | `ST_CoverageClean` resolve |
| **Layered overlapping** | Sobreposição é informação relevante, não erro | CAR, SIGEF | Não é coverage. Tratamento especial (seção 7.6) |
| **Pseudo-coverage** | Coverage por categoria, mas categorias se sobrepõem entre si | Desmatamento PRODES anual | Coverage **por ano**, depois compor entre anos |

Essa classificação vai no `layer_registry` e dirige o pipeline.

---

## 4. Decisões técnicas justificadas

### 4.1 Por que `ST_CoverageClean` substitui o dissolve tradicional

Para layers tipo `dirty_coverage`, `ST_CoverageClean` faz em **uma chamada** o que antes exigia `ST_MakeValid` + `ST_SnapToGrid` + `ST_Union` + verificações manuais. É uma window function que altera as edges de uma coverage poligonal para garantir que nenhum polígono se sobreponha, que gaps pequenos sejam fechados, e que todas as edges compartilhadas sejam exatamente idênticas. Os três parâmetros principais:

- `gapMaximumWidth`: controla o fechamento de gaps. Gaps menores que essa tolerância são fechados.
- `snappingDistance`: controla o snap de vértices próximos. Default `-1` aplica snapping automático baseado em análise da entrada. Use `0.0` para desativar.
- `overlapMergeStrategy`: define o algoritmo para decidir em qual polígono vizinho mesclar áreas sobrepostas (`MERGE_LONGEST_BORDER` é o default).

Para o Brasil, com layers tipicamente em SRID 5880 (metros), uma configuração razoável:

```sql
ST_CoverageClean(
  geom,
  gapMaximumWidth   => 1.0,                      -- fecha gaps até 1m
  snappingDistance  => 0.1,                      -- snap de vértices a 10cm
  overlapMergeStrategy => 'MERGE_LONGEST_BORDER'
) OVER ()
```

**Atenção:** é window function. A partição `OVER ()` significa "toda a tabela como uma única partição". Para particionar por tile/região, usar `OVER (PARTITION BY <chave>)`.

### 4.2 Por que `ST_CoverageInvalidEdges` é a única ferramenta de QA que importa

Window function que checa se os polígonos na partição formam uma coverage poligonal válida. Retorna indicadores lineares (MULTILINESTRING) mostrando a localização de edges inválidas. Polígonos coverage-válidos retornam NULL. Geometrias não-poligonais ou vazias também retornam NULL.

Substitui múltiplos testes manuais:
- Detecta sobreposições silenciosas
- Detecta gaps mínimos
- Detecta edges não-matched (vertex mismatch)
- Pode rodar antes e depois de `ST_CoverageClean` para confirmar limpeza

Vira teste `dbt test` direto:

```sql
-- tests/coverage_is_valid.sql
SELECT canon_id
FROM {{ ref('canonical_ti') }}
WHERE ST_CoverageInvalidEdges(geom) OVER (PARTITION BY tile_id) IS NOT NULL
```

Se retornar zero linhas, a coverage está válida em cada tile.

### 4.3 Por que `ST_CoverageUnion` substitui `ST_Union` em layers de coverage

Para gerar o dissolve total de uma layer (apenas a "casca" externa, sem subdivisões internas), `ST_CoverageUnion` é dramaticamente mais rápido. Em benchmark documentado pelo desenvolvedor do PostGIS, processando 123k polígonos com 3.5M de vértices: ~1.8s com `ST_CoverageUnion` vs ~95s com `ST_Union`. Diferença de ~50x.

**Pré-requisito:** a entrada deve ser coverage válida. Daí a sequência ser sempre `ST_CoverageClean` → `ST_CoverageInvalidEdges` (QA) → `ST_CoverageUnion` quando aplicável.

### 4.4 Por que `ST_CoverageSimplify` é opcional mas valioso

Window function que simplifica as edges dos polígonos em uma coverage poligonal, preservando a topologia. Os polígonos simplificados resultantes são consistentes ao longo das edges compartilhadas e ainda formam coverage válida. O parâmetro tolerance tem unidades de distância. Usa variante do algoritmo Visvalingam-Whyatt. Para simplificar apenas edges "internas" (compartilhadas por dois polígonos) usar `simplifyBoundary => false`.

Útil para:
- Marts de visualização (gerar versões leves para mapas)
- Reduzir custo de overlay em consultas analíticas tolerantes a erro
- Reduzir tamanho de armazenamento em camadas com fronteiras muito detalhadas

**Nunca usar na canônica principal** — o pipeline canônico precisa preservar precisão original.

### 4.5 Por que `ST_Polygonize` continua na composição final

A família `ST_Coverage*` opera **dentro de uma layer**. Para combinar N layers em fragmentos mínimos comuns, ainda precisamos do overlay tradicional:

1. Cada canônica vira coverage limpa via `ST_CoverageClean` (ou já é nativa)
2. Os boundaries de todas as canônicas + borda do tile entram em `ST_Boundary`
3. `ST_Node + ST_UnaryUnion` limpa cruzamentos
4. `ST_Polygonize` reconstrói os fragmentos mínimos
5. Atribuição via `ST_PointOnSurface + ST_Contains` por LEFT JOIN

Não existe `ST_CoverageOverlay` multi-layer no PostGIS atual. Esse passo continua sendo o gargalo (e por isso é paralelizado por tile).

### 4.6 Funções descartadas

| Função | Por que não |
|---|---|
| `ST_DumpSegments` | Quebra arestas em segmentos atômicos de 2 pontos. Explode cardinalidade. `ST_Polygonize` já nodifica internamente. |
| `ST_DumpRings` | Útil para inspeção, mas `ST_Boundary` já entrega o linework correto incluindo holes em uma chamada. |
| `ST_Union` (cascaded tradicional) | Substituído por `ST_CoverageUnion` onde aplicável; fica como fallback para layers `layered_overlapping`. |
| `ST_MakeValid` standalone | Continua sendo aplicado no staging, mas `ST_CoverageClean` cobre os casos restantes dentro de coverage. |

---

## 5. Estrutura do projeto dbt

```
geo_pipeline/
├── dbt_project.yml
├── profiles.yml                   # outputs: duckdb, postgres
├── packages.yml
│
├── seeds/
│   └── layer_registry.csv         # metadados das N layers
│
├── macros/
│   ├── layer_registry.sql         # leitura do registry
│   ├── union_boundaries.sql       # gera UNION ALL dos boundaries para N layers
│   ├── attribution_joins.sql      # gera LEFT JOINs da atribuição final
│   ├── coverage_clean_macro.sql   # wrapper de ST_CoverageClean parametrizado
│   └── coverage_qa.sql            # gera testes ST_CoverageInvalidEdges
│
├── models/
│   ├── staging/                   # adapter: duckdb
│   ├── canonical/                 # adapter: postgres (PostGIS 3.6+)
│   ├── grid/                      # adapter: postgres
│   ├── overlay/                   # adapter: postgres
│   ├── consolidation/             # adapter: postgres
│   └── marts/                     # adapter: postgres
│
├── tests/
│   ├── coverage_valid_per_layer.sql
│   ├── area_conservada.sql
│   └── cobertura_completa.sql
│
└── orchestrator.py
```

**Nota sobre adapter:** as operações `ST_Coverage*` rodam em PostGIS, não em DuckDB. Por isso a camada canônica migra do DuckDB para o Postgres. DuckDB fica restrito ao staging — leitura de parquet, validação básica, reprojeção.

---

## 6. Registry de layers

```csv
# seeds/layer_registry.csv
name,source_path,coverage_type,id_field,attrs,gap_tolerance,snap_distance,description
municipios,sources/ibge_mun.parquet,native_coverage,cod_ibge,"nome,uf,bioma",0,0,Malha municipal IBGE
biomas,sources/biomas.parquet,native_coverage,bioma_id,"nome",0,0,Biomas IBGE
ti,sources/ti.parquet,dirty_coverage,terra_id,"etnia,fase,modalidade",1.0,0.1,Terras Indígenas FUNAI
uc,sources/uc.parquet,dirty_coverage,uc_id,"categoria,grupo,bioma,esfera",1.0,0.1,Unidades de Conservação
desmatamento,sources/prodes.parquet,pseudo_coverage,desmat_id,"ano,classe,bioma",0.5,0.05,PRODES (coverage por ano)
car,sources/car.parquet,layered_overlapping,cod_imovel,"tipo,modulo_fiscal,municipio,situacao",-,-,Cadastro Ambiental Rural
sigef,sources/sigef.parquet,layered_overlapping,parcela_id,"situacao,detentor_tipo,area_registrada",-,-,SIGEF parcelas certificadas
```

Quatro tipos de `coverage_type` resultam em quatro templates canônicos distintos.

---

## 7. Pipeline detalhado

### 7.1 Staging (DuckDB)

Por layer, modelo `stg_<layer>` que:
- Lê parquet via `read_parquet()`
- Valida WKT/WKB → geometria
- Aplica `ST_MakeValid` (DuckDB spatial)
- Reprojeta para **SRID 5880** (Albers Brasil, preserva área)
- Padroniza colunas conforme registry
- **Não** atribui `tile_id` aqui — fica para a canônica em Postgres

Saída materializada em parquet e carregada no Postgres via `ogr2ogr` ou `pg_parquet`.

**Testes:** `not_null` em `id`/`geom`, `unique` em `id`, `ST_IsValid(geom)`, SRID correto.

### 7.2 Grid de referência (Postgres)

Modelo `grid_brasil`, materializado uma única vez:

```sql
{{ config(materialized='table', meta={'adapter': 'postgres'}) }}

WITH bbox AS (
  SELECT
    generate_series(-74.0, -34.0, 0.5)::numeric AS lon,
    generate_series(-34.0,   6.0,  0.5)::numeric AS lat
),
candidates AS (
  SELECT
    ROW_NUMBER() OVER (ORDER BY lat, lon) AS tile_id,
    ST_Transform(
      ST_MakeEnvelope(lon, lat, lon + 0.5, lat + 0.5, 4326),
      5880
    ) AS geom
  FROM bbox
)
SELECT c.tile_id, c.geom
FROM candidates c
JOIN {{ ref('br_outline') }} b ON ST_Intersects(c.geom, b.geom)
```

Resultado: ~700 tiles cobrindo apenas o BR. Indexar com `GIST(geom)` e `BTREE(tile_id)`.

### 7.3 Canônica — Native Coverage (municípios, biomas)

Mais simples. Apenas QA + carregamento.

```sql
-- canonical_municipios.sql
{{ config(
    materialized='table',
    meta={'adapter': 'postgres'},
    post_hook=[
      "CREATE INDEX ON {{ this }} USING GIST(geom)",
      "CREATE INDEX ON {{ this }} (tile_id)"
    ]
) }}

WITH validated AS (
  SELECT
    cod_ibge,
    nome, uf, bioma,
    geom,
    -- QA: edges inválidas devem ser NULL
    ST_CoverageInvalidEdges(geom) OVER () AS invalid_edges
  FROM {{ ref('stg_municipios') }}
),
clipped AS (
  SELECT
    v.cod_ibge,
    v.nome, v.uf, v.bioma,
    g.tile_id,
    (ST_Dump(ST_Intersection(v.geom, g.geom))).geom AS geom
  FROM validated v
  JOIN {{ ref('grid_brasil') }} g ON ST_Intersects(v.geom, g.geom)
  WHERE v.invalid_edges IS NULL
    AND NOT ST_IsEmpty(ST_Intersection(v.geom, g.geom))
)
SELECT
  md5(tile_id::text || cod_ibge) AS canon_id,
  tile_id,
  ARRAY[cod_ibge] AS source_ids,
  nome, uf, bioma,
  geom,
  ST_Area(geom) / 10000 AS area_ha
FROM clipped
```

### 7.4 Canônica — Dirty Coverage (TI, UC)

Aqui `ST_CoverageClean` faz o trabalho pesado.

```sql
-- canonical_ti.sql
{{ config(materialized='table', meta={'adapter': 'postgres'}) }}

WITH layer_meta AS (
  SELECT * FROM {{ ref('layer_registry') }} WHERE name = 'ti'
),
-- Passo 1: limpa a coverage globalmente (antes do tiling)
cleaned AS (
  SELECT
    terra_id,
    etnia, fase, modalidade,
    ST_CoverageClean(
      geom,
      gapMaximumWidth      => 1.0,
      snappingDistance     => 0.1,
      overlapMergeStrategy => 'MERGE_LONGEST_BORDER'
    ) OVER () AS geom
  FROM {{ ref('stg_ti') }}
),
-- Passo 2: QA pós-limpeza
qa AS (
  SELECT
    *,
    ST_CoverageInvalidEdges(geom) OVER () AS invalid_edges
  FROM cleaned
),
-- Passo 3: recorte por tile
clipped AS (
  SELECT
    q.terra_id,
    q.etnia, q.fase, q.modalidade,
    g.tile_id,
    (ST_Dump(ST_Intersection(q.geom, g.geom))).geom AS geom
  FROM qa q
  JOIN {{ ref('grid_brasil') }} g ON ST_Intersects(q.geom, g.geom)
  WHERE q.invalid_edges IS NULL
    AND NOT ST_IsEmpty(ST_Intersection(q.geom, g.geom))
)
SELECT
  md5(tile_id::text || terra_id) AS canon_id,
  tile_id,
  ARRAY[terra_id] AS source_ids,
  etnia, fase, modalidade,
  geom,
  ST_Area(geom) / 10000 AS area_ha
FROM clipped
```

**Observação importante sobre ordem:** `ST_CoverageClean` é aplicado **antes** do recorte por tile, sobre a layer inteira no SRID nativo. Limpar coverage tile-a-tile criaria descontinuidades nas fronteiras. Para layers muito grandes onde a limpeza global estoura memória, particionar por região maior (por bioma ou UF) e limpar separadamente — aceitando que as fronteiras dessas regiões podem ter pequenas inconsistências.

### 7.5 Canônica — Pseudo Coverage (PRODES)

Coverage por ano. Limpa cada ano, depois compõe.

```sql
-- canonical_desmatamento.sql
{{ config(materialized='table', meta={'adapter': 'postgres'}) }}

WITH cleaned_per_year AS (
  SELECT
    desmat_id,
    ano, classe, bioma,
    -- particiona por ano: cada ano é coverage limpa independente
    ST_CoverageClean(
      geom,
      gapMaximumWidth      => 0.5,
      snappingDistance     => 0.05
    ) OVER (PARTITION BY ano) AS geom
  FROM {{ ref('stg_desmatamento') }}
),
qa AS (
  SELECT
    *,
    ST_CoverageInvalidEdges(geom) OVER (PARTITION BY ano) AS invalid_edges
  FROM cleaned_per_year
),
clipped AS (
  SELECT
    q.desmat_id,
    q.ano, q.classe, q.bioma,
    g.tile_id,
    (ST_Dump(ST_Intersection(q.geom, g.geom))).geom AS geom
  FROM qa q
  JOIN {{ ref('grid_brasil') }} g ON ST_Intersects(q.geom, g.geom)
  WHERE q.invalid_edges IS NULL
    AND NOT ST_IsEmpty(ST_Intersection(q.geom, g.geom))
)
SELECT
  md5(tile_id::text || desmat_id::text) AS canon_id,
  tile_id,
  ARRAY[desmat_id] AS source_ids,
  ano, classe, bioma,
  geom,
  ST_Area(geom) / 10000 AS area_ha
FROM clipped
```

Polígonos de anos diferentes podem se sobrepor (área desmatada em 2018 e novamente em 2022). Isso é tratado no overlay final.

### 7.6 Canônica — Layered Overlapping (CAR, SIGEF)

Caso mais complexo. Sobreposições internas não devem ser removidas — são informação.

`ST_CoverageClean` **não se aplica** porque pressupõe que sobreposições são erros. Aqui usamos a abordagem boundary + polygonize por dentro da própria layer.

```sql
-- canonical_car.sql
{{ config(materialized='table', meta={'adapter': 'postgres'}) }}

WITH clipped AS (
  SELECT
    s.cod_imovel,
    s.tipo, s.modulo_fiscal, s.municipio, s.situacao,
    g.tile_id,
    (ST_Dump(ST_Intersection(s.geom, g.geom))).geom AS geom
  FROM {{ ref('stg_car') }} s
  JOIN {{ ref('grid_brasil') }} g ON ST_Intersects(s.geom, g.geom)
  WHERE NOT ST_IsEmpty(ST_Intersection(s.geom, g.geom))
),
-- Boundaries de todos os polígonos no tile, nodados
boundaries AS (
  SELECT
    tile_id,
    ST_Node(ST_UnaryUnion(ST_Collect(ST_Boundary(geom)))) AS lines
  FROM clipped
  GROUP BY tile_id
),
-- Fragmentos mínimos dentro da layer (interseções de CARs)
fragments AS (
  SELECT
    tile_id,
    (ST_Dump(ST_Polygonize(lines))).geom AS geom
  FROM boundaries
),
-- Atribuição: quais CARs originais cobrem cada fragmento
attributed AS (
  SELECT
    f.tile_id,
    f.geom,
    ARRAY_AGG(c.cod_imovel ORDER BY c.cod_imovel) AS source_ids,
    -- atributos como array completo: sobreposição entre CARs é objeto de análise
    ARRAY_AGG(c.tipo ORDER BY c.cod_imovel)           AS tipo,
    ARRAY_AGG(c.modulo_fiscal ORDER BY c.cod_imovel)  AS modulo_fiscal,
    ARRAY_AGG(c.municipio ORDER BY c.cod_imovel)      AS municipio,
    ARRAY_AGG(c.situacao ORDER BY c.cod_imovel)       AS situacao,
    COUNT(*)                                          AS n_sobreposicoes
  FROM fragments f
  JOIN clipped c
    ON c.tile_id = f.tile_id
    AND ST_Contains(c.geom, ST_PointOnSurface(f.geom))
  GROUP BY f.tile_id, f.geom
)
SELECT
  md5(tile_id::text || ST_AsBinary(geom)) AS canon_id,
  tile_id,
  source_ids,
  tipo, modulo_fiscal, municipio, situacao,
  n_sobreposicoes,
  geom,
  ST_Area(geom) / 10000 AS area_ha
FROM attributed
```

A canônica resultante **é uma coverage limpa** (fragmentos não se sobrepõem entre si dentro do tile). Pode passar por `ST_CoverageInvalidEdges` como QA opcional.

### 7.7 Overlay multi-layer (Postgres)

A composição entre canônicas. Funções `ST_Coverage*` não cobrem isso — voltamos ao `ST_Polygonize`, mas agora com input já pré-processado e validado.

**`tile_boundaries`** (incremental por tile):

```sql
{{ config(
    materialized='incremental',
    unique_key='tile_id',
    meta={'adapter': 'postgres'}
) }}

WITH all_lines AS (
  {{ union_boundaries_macro(var('active_tile_id')) }}
),
nodded AS (
  SELECT
    {{ var('active_tile_id') }} AS tile_id,
    ST_Node(ST_UnaryUnion(ST_Collect(geom))) AS lines
  FROM all_lines
)
SELECT * FROM nodded
```

A macro `union_boundaries_macro` itera sobre o registry:

```jinja
{% macro union_boundaries_macro(tile_id) %}
  {% set layers = layer_registry() %}
  {% for layer in layers %}
    SELECT ST_Boundary(geom) AS geom
    FROM {{ ref('canonical_' ~ layer.name) }}
    WHERE tile_id = {{ tile_id }}
    {{ 'UNION ALL' if not loop.last }}
  {% endfor %}
  UNION ALL
  SELECT ST_Boundary(geom) FROM {{ ref('grid_brasil') }}
  WHERE tile_id = {{ tile_id }}
{% endmacro %}
```

**`tile_fragments`:**

```sql
SELECT
  tile_id,
  ROW_NUMBER() OVER (PARTITION BY tile_id) AS frag_seq,
  (ST_Dump(ST_Polygonize(lines))).geom AS geom
FROM {{ ref('tile_boundaries') }}
WHERE tile_id = {{ var('active_tile_id') }}
```

**`tile_attribution`** (atribuição N layers):

```sql
{{ config(materialized='incremental', unique_key=['tile_id', 'frag_seq']) }}

SELECT
  f.tile_id,
  f.frag_seq,
  f.geom,
  ST_Area(f.geom) / 10000 AS area_ha,
  {{ attribution_columns_macro() }}
FROM {{ ref('tile_fragments') }} f
{{ attribution_joins_macro() }}
WHERE f.tile_id = {{ var('active_tile_id') }}
```

### 7.8 Consolidação

```sql
-- analytical_base.sql
{{ config(
    materialized='table',
    post_hook=[
      "CREATE INDEX ON {{ this }} USING GIST(geom)",
      "CREATE INDEX ON {{ this }} (tile_id)",
      "{{ partial_indexes_per_layer() }}"
    ]
) }}

SELECT * FROM {{ ref('tile_attribution') }}
```

Particionar por UF via `LIST PARTITION` para consultas regionais. Atribuição da UF via `canonical_municipios` integrada.

### 7.9 Marts

Marts temáticos como materialized views. Exemplo:

```sql
-- marts/sobreposicao_car_ti.sql
{{ config(materialized='materialized_view') }}

SELECT
  ti_etnia[1] AS etnia,
  ti_fase[1] AS fase,
  COUNT(*) AS qtd_fragmentos,
  SUM(area_ha) AS area_sobreposicao_ha,
  -- cardinalidade de CARs envolvidos (array completo)
  SUM(array_length(car_source_ids, 1)) AS total_cars_envolvidos
FROM {{ ref('analytical_base') }}
WHERE car_source_ids IS NOT NULL
  AND ti_canon_id IS NOT NULL
GROUP BY ti_etnia[1], ti_fase[1]
```

Para marts de visualização, usar `ST_CoverageSimplify` como passo final:

```sql
-- marts/uc_simplificado_para_mapa.sql
{{ config(materialized='materialized_view') }}

SELECT
  uc_id,
  categoria,
  grupo,
  ST_CoverageSimplify(geom, 50) OVER () AS geom_simplificado
FROM {{ ref('canonical_uc') }}
```

Tolerância 50 metros para visualização web em zoom regional.

---

## 8. Fallbacks quando `ST_Coverage*` não está disponível

Se a versão de GEOS for inferior a 3.14, partes do pipeline precisam de fallback:

| Função | GEOS mín | Fallback |
|---|---|---|
| `ST_CoverageUnion` | 3.12 | `ST_Union` cascaded particionado por `ST_GeoHash` |
| `ST_CoverageInvalidEdges` | 3.12 | Self-join `ST_Overlaps` (muito mais lento) + check de `ST_IsValid` |
| `ST_CoverageSimplify` | 3.12 | `ST_SimplifyPreserveTopology` (não preserva edges compartilhadas — gaps aparecem) |
| `ST_CoverageClean` | 3.14 | `ST_MakeValid` + `ST_SnapToGrid` + dedup manual (perde resolução de gaps) |

**Recomendação forte:** instalar GEOS 3.14+. Os fallbacks comprometem qualidade e velocidade significativamente.

---

## 9. Orquestração

```python
# orchestrator.py
import subprocess, json
from concurrent.futures import ProcessPoolExecutor, as_completed
import psycopg2

def run_dbt(select, target, vars_dict=None):
    cmd = ["dbt", "run", "--select", select, "--target", target]
    if vars_dict:
        cmd += ["--vars", json.dumps(vars_dict)]
    return subprocess.run(cmd, capture_output=True, text=True)

def get_tiles():
    conn = psycopg2.connect("dbname=geodata")
    cur = conn.cursor()
    cur.execute("SELECT tile_id FROM grid_brasil ORDER BY tile_id")
    return [r[0] for r in cur.fetchall()]

def process_tile(tile_id):
    return tile_id, run_dbt(
        select="overlay.*",
        target="postgres",
        vars_dict={"active_tile_id": tile_id}
    )

def main():
    # 1. Staging no DuckDB
    run_dbt("staging.*", "duckdb")

    # 2. Carrega parquets exportados no PostGIS
    load_parquet_to_postgis()

    # 3. Grid + Canônicas no Postgres (com ST_Coverage*)
    run_dbt("grid.* canonical.*", "postgres")

    # 4. Valida coverage por layer antes do overlay
    run_dbt_test(select="canonical")

    # 5. Overlay multi-layer paralelizado por tile
    tiles = get_tiles()
    failed = []
    with ProcessPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(process_tile, t): t for t in tiles}
        for fut in as_completed(futures):
            tile_id, result = fut.result()
            if result.returncode != 0:
                failed.append((tile_id, result.stderr))

    if failed:
        save_failure_log(failed)
        return

    # 6. Consolidação e marts
    run_dbt("consolidation.* marts.*", "postgres")
    run_dbt_test()

if __name__ == "__main__":
    main()
```

---

## 10. Tuning de PostgreSQL

```ini
# postgresql.conf
shared_buffers = 25% RAM
work_mem = 512MB                # ST_CoverageClean é memória-intensivo
maintenance_work_mem = 4GB
max_parallel_workers = 16
max_parallel_workers_per_gather = 4
effective_cache_size = 75% RAM
random_page_cost = 1.1
checkpoint_timeout = 30min
max_wal_size = 16GB
```

Particularmente importante: `work_mem` alto é necessário para `ST_CoverageClean` em layers grandes. Se aparecer "out of memory", ou subir work_mem ou particionar a layer antes da limpeza.

---

## 11. Testes de integridade

### Teste primário: validade de coverage

```sql
-- tests/canonical_is_valid_coverage.sql (gerado por macro para cada canônica)
{% for layer in layer_registry() %}
{% if layer.coverage_type in ['native_coverage', 'dirty_coverage', 'layered_overlapping'] %}
SELECT canon_id
FROM {{ ref('canonical_' ~ layer.name) }}
WHERE ST_CoverageInvalidEdges(geom) OVER (PARTITION BY tile_id) IS NOT NULL
{{ 'UNION ALL' if not loop.last }}
{% endif %}
{% endfor %}
```

### Conservação de área

```sql
-- A soma das áreas dos fragmentos por tile = área do tile
SELECT tile_id
FROM (
  SELECT tile_id, SUM(area_ha) AS soma
  FROM {{ ref('tile_attribution') }}
  GROUP BY tile_id
) f
JOIN (
  SELECT tile_id, ST_Area(geom)/10000 AS area
  FROM {{ ref('grid_brasil') }}
) g USING (tile_id)
WHERE ABS(f.soma - g.area) > 0.001 * g.area
```

### Cobertura completa

```sql
-- Não pode haver buracos no overlay (cada ponto do tile está em algum fragmento)
SELECT tile_id
FROM {{ ref('grid_brasil') }} g
WHERE NOT EXISTS (
  SELECT 1 FROM {{ ref('tile_attribution') }} f
  WHERE f.tile_id = g.tile_id
    AND ST_Contains(ST_Union(f.geom), g.geom)
)
```

---

## 12. Workflow para adicionar layer nova

1. Definir `coverage_type` (`native_coverage`, `dirty_coverage`, `pseudo_coverage`, `layered_overlapping`)
2. Adicionar linha em `seeds/layer_registry.csv` com tolerâncias adequadas
3. `dbt seed`
4. Criar `stg_<nova_layer>.sql` (template DuckDB)
5. Criar `canonical_<nova_layer>.sql` (template Postgres conforme tipo)
6. Executar:
   ```bash
   dbt run --select +canonical_<nova_layer>
   dbt test --select canonical_<nova_layer>     # valida coverage
   python orchestrator.py --reprocess-tiles
   dbt run --select consolidation.* marts.*
   ```

Macros do overlay leem do registry automaticamente.

---

## 13. Limitações conhecidas

| Limitação | Mitigação |
|---|---|
| `ST_CoverageClean` requer GEOS 3.14+ | Verificar com `postgis_full_version()` antes de iniciar. Sem isso, fallback degrada qualidade. |
| Memória em layers gigantes para `ST_CoverageClean OVER ()` | Particionar por bioma/UF antes da limpeza; aceitar microinconsistências nas fronteiras dessas partições |
| Layers `layered_overlapping` (CAR) não se beneficiam de `ST_Coverage*` | Mantêm o pipeline boundary+polygonize tradicional |
| `gapMaximumWidth` pode fechar gaps que **deveriam** existir (rios, estradas) | Ajustar tolerâncias por layer no registry. Em caso de dúvida, gap = 0 |
| `overlapMergeStrategy` afeta atribuição quando há overlaps reais | Em layer `dirty_coverage` o esperado é não haver overlaps; se aparecem, investigar dados de entrada antes de aceitar `MERGE_LONGEST_BORDER` |
| Tiles muito populados demoram desproporcionalmente | Sub-tilear (0.25°) tiles que excedem N fragmentos |
| Atualização de layer força reprocessar tiles afetados | Manter mapa `layer × tiles` e reprocessar subset |

---

## 14. Ordem de implementação sugerida

1. Validar versão de GEOS no servidor de destino (1 dia)
2. Grid de referência (1 dia)
3. Staging das primeiras 2-3 layers (2-3 dias)
4. Canônica `native_coverage` (municípios) — mais simples, valida pipeline base (2 dias)
5. Canônica `dirty_coverage` (TI, UC) — exercita `ST_CoverageClean` (3-5 dias)
6. Canônica `pseudo_coverage` (PRODES) — exercita partição temporal (3 dias)
7. Canônica `layered_overlapping` (CAR, SIGEF) — mais complexa (1-2 semanas)
8. Overlay multi-layer + macros Jinja para N layers (1 semana)
9. Orchestrator Python + paralelização (3-5 dias)
10. Consolidação + marts iniciais (1 semana)
11. Suite de testes via `ST_CoverageInvalidEdges` (contínuo)

---

## 15. Piloto canônica: SICAR SP + AL (próximo milestone)

A primeira materialização real da camada **silver** (canônica em PostGIS) é um piloto restrito a duas UFs do SICAR: **SP** (alta densidade, stress test) e **AL** (UF pequena, iteração rápida). O objetivo é validar o template `layered_overlapping` (§7.6) end-to-end com dados reais antes de escalar para 27 UFs ou adicionar outras layers.

### 15.1 Por que SICAR e por que SP + AL

- **SICAR é `layered_overlapping`**: CARs se sobrepõem por desenho (reivindicações concorrentes, retificações). Exercita o caminho mais complexo do blueprint (boundary + polygonize + atribuição agregada) — se isso funciona, os tipos `dirty_coverage` e `native_coverage` são derivados mais simples.
- **SP**: ~3M+ imóveis, expõe gargalos de memória/tempo no `ST_Polygonize` por tile.
- **AL**: ~150k imóveis, permite iterar a lógica do template em minutos antes de rodar SP.
- **Ambos no mesmo template**: prova que o modelo escala por UF sem mudança de código.

### 15.2 Pré-requisitos

- PostgreSQL 14+ com PostGIS 3.6+ / GEOS 3.14+ instalado local (validar com `SELECT postgis_full_version()`).
- `data/bronze/sicar/sp.parquet` e `data/bronze/sicar/al.parquet` já presentes (rodar `terrasync ingest --source sicar --layers sp al` se faltar).
- `stg_sicar` materializado em `data/staging/stg_sicar.parquet` (já existe via `dbt run --select stg_sicar`).
- `dbt-postgres` adicionado como dependência; profile `postgres` configurado em `profiles.yml`.

### 15.3 Atribuição de UF e carregamento no Postgres

`stg_sicar` hoje lê `data/bronze/sicar/*.parquet` sem preservar a UF de origem. Para o piloto, dois caminhos são aceitos (escolha durante implementação):

- **(a)** Adicionar `filename=true` ao `read_parquet` dentro de uma variante `stg_sicar_uf` que extrai `uf` do basename do arquivo.
- **(b)** Filtrar no nível bronze: criar `stg_sicar_pilot` que lê apenas `sp.parquet` e `al.parquet` e injeta `uf` por `UNION ALL` com literal.

Carregamento staging → Postgres via `ogr2ogr` (rota inicial) ou `pg_parquet` (se disponível na instância). Schema destino: `silver.stg_sicar_pilot(uf, cod_imovel, ..., geom geometry(MultiPolygon, 4326))` com `GIST(geom)` e `BTREE(uf, cod_imovel)`.

### 15.4 Grid restrito ao piloto

Em vez do `grid_brasil` completo (~700 tiles), gerar `grid_pilot` apenas com tiles que intersectam SP ∪ AL — ~80 tiles a 0.5°. Permite paralelizar overlay sem montar a malha continental antes da hora.

```sql
-- models/silver/grid_pilot.sql (pilot only)
WITH uf_outline AS (
  SELECT ST_Union(geom) AS geom
  FROM {{ ref('br_uf_outline') }}      -- seed/source com malha de UFs
  WHERE sigla IN ('SP', 'AL')
)
SELECT g.tile_id, g.geom
FROM {{ ref('grid_brasil') }} g
JOIN uf_outline u ON ST_Intersects(g.geom, u.geom)
```

### 15.5 Modelo canônico

`models/silver/canonical_sicar.sql` segue exatamente o template §7.6 (`layered_overlapping`), com duas adaptações de piloto:

- Filtro `WHERE s.uf IN ('SP', 'AL')` na CTE `clipped`.
- `JOIN {{ ref('grid_pilot') }}` em vez de `grid_brasil`.

Saída: tabela `silver.canonical_sicar` com `canon_id, tile_id, source_ids[], tipo[], modulo_fiscal[], municipio[], situacao[], n_sobreposicoes, geom, area_ha`. Indexar `GIST(geom)`, `BTREE(tile_id)`, `GIN(source_ids)`.

### 15.6 Testes obrigatórios do piloto

| Teste | Critério |
|---|---|
| **Coverage válida dos fragmentos** | `ST_CoverageInvalidEdges(geom) OVER (PARTITION BY tile_id) IS NULL` em todas as linhas |
| **Conservação de área por imóvel** | Para cada `cod_imovel` original: `SUM(area_ha dos fragmentos onde cod_imovel ∈ source_ids) ≈ area_original` (tolerância 0.1%) |
| **Sobreposições detectadas** | Existe pelo menos 1 fragmento com `n_sobreposicoes >= 2` em SP (prova que o overlay capta sobreposição real, não só recorte por tile) |
| **Cobertura completa da UF** | Soma `area_ha` por `tile_id` em `canonical_sicar` ≈ área CAR original recortada pelos tiles (não pode haver gaps internos no `Polygonize`) |
| **Tipo geométrico uniforme** | `ST_GeometryType(geom)` ∈ `{ST_Polygon}` após o `ST_Dump` |

Testes implementados como `.sql` em `tests/silver/` — falha = retorno de linhas.

### 15.7 Critérios de sucesso

- `dbt run --select +canonical_sicar --target postgres` completa para SP + AL.
- Todos os testes do §15.6 passam em ambas as UFs.
- Tempo de SP documentado (baseline para decidir se sub-tilear 0.25° é necessário antes de escalar).
- Pico de memória do worker Postgres documentado (calibra `work_mem` para o rollout).

### 15.8 Fora do escopo do piloto

- Demais 25 UFs do SICAR (rollout pós-piloto).
- Outras canônicas (`canonical_funai`, `canonical_uc`, etc.) — só depois que o template `layered_overlapping` estiver validado.
- Overlay multi-layer (CAR × TI, CAR × PRODES) — depende de outras canônicas existirem.
- Marts gold, materialized views, API.
- Orquestração paralela por tile (`orchestrator.py` §9) — piloto roda single-threaded.
- `seeds/layer_registry.csv` — fica adiado; piloto referencia parâmetros inline no modelo.

### 15.9 Saída esperada para o rollout

Ao final do piloto, devem estar definidos com base em medição (não em estimativa):

- Tempo médio por tile em SP → projeção para 27 UFs.
- `work_mem` mínimo para `ST_Polygonize` não estourar no tile mais denso.
- Necessidade (ou não) de sub-tilear 0.25° para tiles densos.
- Decisão sobre `seeds/layer_registry.csv` agora vs. depois do segundo template.
