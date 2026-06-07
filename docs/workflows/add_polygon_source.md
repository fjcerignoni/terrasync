# Adicionar Fonte Poligonal

Receita para integrar uma nova fonte de dados vetoriais poligonais ao pipeline terrasync.
Cobre `zip_shapefile`, `wfs`, e `arcgis_rest` (FeatureServer). Não requer código Python novo.

---

## Quando usar

Use este workflow quando:
- A fonte entrega polígonos (ou multipolígonos) — florestas, propriedades, processos, limites etc.
- O dado não existe ainda no pipeline (bronze + silver)
- Quer reutilizar o silver como base para exports ou futura camada canonical

Para fontes de **pontos** (ex.: focos de calor), veja `add_point_source.md` (usa `clean_point_geometry`).

---

## Arquitetura esperada

```
rawdata/<source>/*.parquet   ← downloader (ingest)
        ↓
bronze/bro_*.sql             ← clean_geometry aqui, uma vez, por layer
        ↓
silver/slv_*.sql             ← UNION ALL de ref(bro_*), sem clean_geometry
```

`clean_geometry` **nunca** é chamada no silver. O silver é exclusivamente
agregação de bronze refs.

---

## Pré-checklist

Antes de escrever código, levantar:

- [ ] URL de download (ZIP, WFS GetCapabilities, ou ArcGIS REST endpoint)
- [ ] EPSG da fonte (geralmente 4674 para dados brasileiros SIRGAS 2000)
- [ ] Tipo de source: `zip_shapefile` / `wfs` / `arcgis_rest`
- [ ] Layer IDs (para multi-layer) ou nome da layer única
- [ ] Encoding do shapefile (se zip): ingerir primeiro com UTF-8 default, inspecionar campos de texto depois
- [ ] Se shapefile: confirmar nomes reais das colunas no .dbf (são uppercase) — não confiar na documentação

---

## Passo 1 — `apps/terrasync/sources.yaml`

Adicionar bloco de provider (se novo) e bloco da source.

```yaml
providers:
  <provider>:
    display_name: "Nome Oficial do Órgão"

sources:
  <source_name>:
    type: zip_shapefile           # ou: wfs | arcgis_rest
    display_name: "Nome Legível"
    description: "Descrição curta do dado."
    category: vegetation          # ex.: vegetation | agriculture | mining | indigenous | infrastructure
    provider: <provider>
    cadence: daily                # ou: weekly | monthly | annual
    epsg: 4674                    # EPSG da fonte — reprojeção para 4326 acontece no bronze
    # encoding: UTF-8             # só para zip_shapefile com encoding não-UTF-8; omitir se desnecessário
    layers:
      - id: <layer_id>
        url: "https://..."
      # - id: <outro_layer>       # adicionar mais layers se necessário
      #   url: "https://..."
```

**Nota sobre encoding:** ignore a documentação do fornecedor. Ingerir com UTF-8 (default) e verificar
manualmente campos de texto como nomes e municípios. Se aparecer sequência como `CARVÃƒO` (double-encoding),
a fonte é realmente UTF-8 e o fornecedor declarou incorretamente; manter UTF-8. Se aparecer `CARV?O`
(perda de dado), aí sim a fonte é CP1252 — declarar `encoding: CP1252`.

---

## Passo 2 — Bronze SQL

Criar `apps/dbt/models/bronze/<provider>/bro_<provider>_<name>.sql`.

`clean_geometry` e `dedup` acontecem **aqui**, nunca no silver.

### Variante A — colunas já em lowercase, sem renomeação

```sql
{{ config(
    materialized='external',
    location=bronze_path('<provider>_<name>', '<layer_id>'),
    tags=['bronze']
) }}

{{
    clean_geometry(
        rawdata_path('<source_name>', glob='<source_name>_<layer_id>.parquet'),
        source_epsg=4674,
        id_columns=['<pk_col>'],
        dedup_id=['<pk_col>'],
        dedup_date='<date_col>'
    )
}}
```

### Variante B — shapefile DBF (uppercase) ou tipagem a corrigir

Usar quando os nomes do .dbf são uppercase ou há casts necessários (ex.: BIGINT → DOUBLE).

```sql
{{ config(
    materialized='external',
    location=bronze_path('<provider>_<name>', '<layer_id>'),
    tags=['bronze']
) }}

{% set source_rel %}
select
    COLUNA_A     as coluna_a,
    COLUNA_B     as coluna_b,
    cast(NUMERO  as double) as numero,   -- corrigir tipo se necessário
    geometry
from read_parquet(
    '{{ rawdata_path("<source_name>", glob="<source_name>_<layer_id>.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['coluna_a', 'coluna_b'],
        dedup_id=['coluna_a'],
        dedup_date='coluna_data'
    )
}}
```

### Variante C — coluna derivada de contexto (biome, tipo, etc.)

Quando a fonte tem múltiplas layers que serão unidas no silver e precisam de
uma coluna identificadora (ex.: `'privado' as tipo`), adicionar como literal no
`source_rel`. O bronze **já sabe** qual layer representa.

```sql
{% set source_rel %}
select
    *,
    'privado' as tipo
from read_parquet(
    '{{ rawdata_path("<source_name>", glob="<source_name>_privado.parquet") }}'
)
{% endset %}

{{
    clean_geometry(
        relation=source_rel,
        source_epsg=4674,
        id_columns=['<pk_col>'],
        dedup_id=['<pk_col>'],
        dedup_date='<date_col>'
    )
}}
```

`clean_geometry` aplica `ST_Force2D` + `ST_MakeValid` + `ST_CollectionExtract(3)` +
`ST_Multi` + reprojeção EPSG:4326. Output sempre `MULTIPOLYGON` em EPSG:4326.

---

## Passo 3 — `apps/dbt/models/bronze/<provider>/schema.yml`

**Antes de escrever**, inspecionar o parquet para confirmar tipos reais:

```python
import pyarrow.parquet as pq
schema = pq.read_schema("data/rawdata/<source_name>/<source_name>_<layer_id>.parquet")
print(schema)
# int32 → INTEGER, int64 → BIGINT, float64 → DOUBLE, string/large_string → VARCHAR
```

```yaml
version: 2
models:
  - name: bro_<provider>_<name>
    description: >-
      Bronze <Provider> <Name> — clean_geometry(rawdata, <epsg>->4326).
      Dedup por <pk_col>, keep mais recente por <date_col>.
    config:
      tags: ['bronze']
    columns:
      - name: stg_id
        data_type: VARCHAR
        description: "Surrogate key MD5 de <pk_col>."
        tests:
          - not_null
          - unique
      - name: <pk_col>
        data_type: VARCHAR
        description: "<Descrição da PK da fonte>."
        tests:
          - not_null
          - unique      # SOMENTE se empiricamente único — confirmar antes
      - name: geometry
        data_type: geometry
        description: "MULTIPOLYGON EPSG:4326 — saida do clean_geometry."
        tests:
          - not_null
```

---

## Passo 4 — Silver SQL

Criar `apps/dbt/models/silver/<provider>/slv_<name>.sql`.

O silver **não chama** `clean_geometry`. É exclusivamente union de refs bronze.

### Fonte com layer única

```sql
{{ config(
    materialized='external',
    location=silver_path('slv_<name>')
) }}

select * from {{ ref('bro_<provider>_<name>') }}
```

### Fonte com múltiplas layers (schema idêntico ou compatível)

```sql
{{ config(
    materialized='external',
    location=silver_path('slv_<name>')
) }}

-- union_by_name alinha schemas se houver colunas opcionais entre layers.
select * from {{ ref('bro_<provider>_<name>_layer1') }}
union all by name
select * from {{ ref('bro_<provider>_<name>_layer2') }}
```

---

## Passo 5 — `apps/dbt/models/silver/<provider>/schema.yml`

```yaml
version: 2
models:
  - name: slv_<name>
    description: >-
      Silver <Provider> <Name> — <descrição>. Geometrias MULTIPOLYGON
      em EPSG:4326 (clean_geometry aplicada na camada bronze).
    columns:
      - name: stg_id
        data_type: VARCHAR
        description: Surrogate key MD5 de <pk_col>.
        tests:
          - not_null
          - unique
      - name: <coluna>
        data_type: VARCHAR   # ou INTEGER / DOUBLE / DATE / TIMESTAMP
        description: ...
        tests:
          - not_null         # somente se o campo não tem NULLs no dado real
      - name: geometry
        data_type: GEOMETRY
        description: Geometria MULTIPOLYGON em EPSG:4326.
        tests:
          - not_null
```

---

## Verificação

```bash
# 1. Ingerir rawdata
uv run terrasync ingest --source <source_name>

# 2. Inspecionar parquet (confirmar colunas, tipos, encoding de strings)
python -c "
import pyarrow.parquet as pq, duckdb
schema = pq.read_schema('data/rawdata/<source_name>/<source_name>_<layer_id>.parquet')
print(schema)
print(duckdb.sql(\"SELECT count(*), count(distinct <id_col>) FROM 'data/rawdata/<source_name>/*.parquet'\").fetchone())
"

# 3. Rodar bronze
uv run terrasync transform --select bro_<provider>_<name>

# 4. Rodar silver
uv run terrasync transform --select slv_<name>

# 5. Confirmar saída
ls data/silver/slv_<name>.parquet
```

---

## Gotchas conhecidos

1. **Encoding shapefile — ignore o fornecedor**
   Documentação frequentemente declara CP1252 quando o arquivo é UTF-8. Ingerir com UTF-8 (default)
   e verificar strings manualmente. Double-encoding é sinal de UTF-8 lido como CP1252 (bytes `C3 83`
   viram "Ã" + "ƒ"). Ver sources.yaml Passo 1 para diagnóstico.

2. **DBF uppercase — sempre usar Variante B**
   Nomes de campo do .dbf são uppercase no arquivo, independente da documentação do fornecedor.
   DuckDB resolve case-insensitively, mas aliases explícitos tornam o schema previsível downstream.

3. **`unique` test — verificar empiricamente**
   ID de feição ≠ PK única. Processos com múltiplos polígonos (SIGMINE), imóveis multi-face (SIGEF),
   alertas multi-evento etc. têm múltiplas linhas por identificador.
   Confirmar: `SELECT count(*), count(distinct <id>) FROM parquet_scan('...')`.

4. **Tipos numéricos — confirmar no parquet**
   Shapefile armazena int32 e float64. Declarar `INTEGER` para int32/int64, `DOUBLE` para float64.
   Não assumir pelos nomes de campo.

5. **Multi-layer com schema divergente**
   Quando layers do mesmo fornecedor têm colunas diferentes (ex.: SICAR 27 UFs sem `data_atualizacao`
   em 12 delas), cada layer vira um bronze separado. O silver usa `union all by name` que preenche
   colunas ausentes com NULL automaticamente.

6. **`clean_geometry` não recebe `SELECT *` implícito na Variante A**
   A macro emite `SELECT * EXCLUDE (geometry), <geom_expr> AS geometry`. Se o source já tem
   uma coluna `geometry`, a variante simples funciona. Se a coluna de geometria tem outro nome,
   declarar alias `AS geometry` no SELECT da Variante B.

7. **`ST_Force2D` não precisa ser chamado manualmente**
   `clean_geometry` já aplica `ST_Force2D` internamente. Não adicionar no `source_rel`.
