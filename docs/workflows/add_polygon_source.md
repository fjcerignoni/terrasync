# Adicionar Fonte Poligonal

Receita para integrar uma nova fonte de dados vetoriais poligonais ao pipeline terrasync.
Cobre `zip_shapefile`, `wfs`, e `arcgis_rest` (FeatureServer). Não requer código Python novo.

---

## Quando usar

Use este workflow quando:
- A fonte entrega polígonos (ou multipolígonos) — florestas, propriedades, processos, limites etc.
- O dado não existe ainda no staging (`apps/dbt/models/staging/`)
- Quer reutilizar o staging como base para exports ou futura camada silver

Para fontes de **pontos** (ex.: focos de calor), veja `add_point_source.md` (usa `clean_point_geometry`).

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
    epsg: 4674                    # EPSG da fonte — reprojetar para 4326 acontece no staging
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

## Passo 2 — `apps/dbt/models/staging/<provider>/sources.yml`

Cria (ou adiciona a) o arquivo de declaração dbt que aponta para o parquet rawdata.

```yaml
version: 2

sources:
  - name: rawdata_<provider>
    description: Rawdata <Provider> — parquets baixados pelo terrasync ingest.
    tables:
      - name: <source_name>
        description: <Descrição da layer>.
        meta:
          external_location: "read_parquet('{{ env_var('TERRASYNC_DATA_ROOT', '../../data') }}/rawdata/<source_name>/<source_name>_<layer_id>.parquet')"
```

**Path pattern:** `rawdata/<source_name>/<source_name>_<layer_id>.parquet`
Confirmar o path exato após o ingest com `ls data/rawdata/<source_name>/`.

**Multi-layer (layers separadas = tabelas separadas):**
```yaml
    tables:
      - name: <source_name>_layer1
        meta:
          external_location: "read_parquet('...rawdata/<source_name>/<source_name>_layer1.parquet')"
      - name: <source_name>_layer2
        meta:
          external_location: "read_parquet('...rawdata/<source_name>/<source_name>_layer2.parquet')"
```

**Multi-layer (layers com schema idêntico = glob union):**
```yaml
        meta:
          external_location: "read_parquet('...rawdata/<source_name>/*.parquet', union_by_name=true, filename=true)"
```

---

## Passo 3 — Staging SQL

Criar `apps/dbt/models/staging/<provider>/stg_<name>.sql`.

### Variante A — simples (colunas já em lowercase, sem necessidade de renomeação)

Usar quando a fonte é WFS ou ArcGIS REST (colunas já vêm como declarado).

```sql
{{ config(
    materialized='external',
    location=staging_path('stg_<name>')
) }}

{{ clean_geometry(relation="SELECT * FROM " ~ source('rawdata_<provider>', '<source_name>'), source_epsg=4674) }}
```

### Variante B — column-rename (shapefile DBF ou schema divergente)

Usar quando os nomes de campo do .dbf são uppercase ou precisam de alias para padronizar lowercase.
**Regra geral: sempre usar variante B para `zip_shapefile`.**

```sql
{{ config(
    materialized='external',
    location=staging_path('stg_<name>')
) }}

-- Colunas renomeadas para lowercase; case original do .dbf pode variar —
-- DuckDB resolve via case-insensitive matching no read_parquet.
{% set source_rel %}
SELECT
    COLUNA_A     AS coluna_a,
    COLUNA_B     AS coluna_b,
    ColunaC      AS coluna_c,    -- DuckDB aceita qualquer case no SELECT
    ...
    geometry
FROM {{ source('rawdata_<provider>', '<source_name>') }}
{% endset %}

{{ clean_geometry(relation=source_rel, source_epsg=4674) }}
```

`clean_geometry` aplica `ST_MakeValid` + `ST_CollectionExtract(3)` + `ST_Multi` + reprojeção EPSG:4326.
Output sempre `MULTIPOLYGON` em EPSG:4326.

---

## Passo 4 — `apps/dbt/models/staging/<provider>/schema.yml`

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
  - name: stg_<name>
    description: >-
      <Descrição completa>. Geometria MULTIPOLYGON em EPSG:4326 via clean_geometry.
    columns:
      - name: <pk_column>
        data_type: VARCHAR
        description: Identificador único <do quê>. (verificar se é realmente único — ver Gotchas)
        tests:
          - not_null
          - unique          # SOMENTE se empiricamente único — confirmar antes
      - name: <coluna2>
        data_type: VARCHAR  # ou INTEGER / DOUBLE / DATE / TIMESTAMP
        description: ...
        tests:
          - not_null        # somente se o campo não tem NULLs no dado real
      - name: geometry
        data_type: GEOMETRY
        description: Geometria MULTIPOLYGON em EPSG:4326.
        tests:
          - not_null
```

**Checklist de testes mínimos por modelo:**
- `not_null` + `unique` na coluna PK (se existir PK real)
- `not_null` em colunas declaradas NOT NULL no schema conceitual
- `accepted_values` para colunas de status/categoria com valores conhecidos
- `not_null` em `geometry`

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

# 3. Rodar staging
uv run terrasync transform --select stg_<name>

# 4. Confirmar saída
ls data/staging/stg_<name>.parquet
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
   Quando layers do mesmo fornecedor têm colunas diferentes (ex.: algumas UFs do SICAR não têm
   `data_atualizacao`), usar `union_by_name=true` no glob e tratar NULLs explicitamente no staging SQL.

6. **`clean_geometry` não recebe `SELECT *` implícito**
   A macro emite `SELECT * EXCLUDE (geometry), <geom_expr> AS geometry`. Se o source já tem
   uma coluna `geometry`, a variante simples funciona. Se a coluna de geometria tem outro nome,
   declarar alias `AS geometry` no SELECT da Variante B.
