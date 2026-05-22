# Adicionar Export de Cliente

Receita para criar um entregável de cliente (parquet versionado) a partir de um staging model existente.

---

## Quando usar

Use este workflow quando:
- Um cliente precisa de um subconjunto ou recorte de um staging model
- O entregável é parquet versionado por data (`v=YYYY-MM-DD`)
- **Não** é transformação analítica complexa (isso seria silver/gold, não export)

**Export vs silver:** export é recorte/seleção de colunas do staging compartilhado para um cliente específico.
Não aplica joins complexos, não é base para outras transformações. Silver (PostGIS, futuro) é o lugar
para isso.

---

## Passo 1 — Export SQL

Criar `apps/dbt/models/exports/<client>/<model_name>.sql`.

```sql
{{ config(
    materialized='external',
    location=export_path('<client>', '<model_name>')
) }}

SELECT
    col1,
    col2,
    col3,
    {{ area_ha('geometry') }} AS area_ha_calc,  -- adicionar se área relevante para o cliente
    geometry
FROM {{ ref('stg_<name>') }}
-- WHERE uf IN ('AC', 'AM', ...)               -- recorte geográfico, se necessário
-- WHERE data_referencia >= '2020-01-01'        -- recorte temporal, se necessário
```

**Regras obrigatórias:**
- Sem `SELECT *`. Listar todas as colunas explicitamente.
- `area_ha_calc` via `{{ area_ha('geometry') }}` usa EPSG:5880 (equal-area Albers BR). O sufixo
  `_calc` distingue de `area_ha` que pode vir da fonte (campo do fornecedor).
- Export referencia sempre o staging via `ref('stg_<name>')`, nunca lê rawdata diretamente.

**Pattern dedup** (quando o staging tem duplicatas por design, ex.: SICAR `cod_imovel` duplicado):

```sql
{{ config(
    materialized='external',
    location=export_path('<client>', '<model_name>')
) }}

WITH ranked AS (
    SELECT
        pk_col,
        col2,
        ...,
        {{ area_ha('geometry') }} AS area_ha_calc,
        geometry,
        row_number() OVER (
            PARTITION BY pk_col
            ORDER BY COALESCE(data_atualizacao, dat_criacao) DESC NULLS LAST,
                     dat_criacao DESC NULLS LAST
        ) AS _rn
    FROM {{ ref('stg_<name>') }}
    -- WHERE ...
)

SELECT
    pk_col, col2, ..., area_ha_calc, geometry
FROM ranked
WHERE _rn = 1
```

---

## Passo 2 — Export YML

Criar `apps/dbt/models/exports/<client>/<model_name>.yml` co-localizado.

```yaml
version: 2

models:
  - name: <model_name>
    description: >-
      Export do cliente <client> / projeto <project>. <Descrição do recorte e propósito>.
      Materializado como parquet versionado em data/exports/<client>/<model_name>/v=YYYY-MM-DD/.
    columns:
      - name: <pk_col>
        data_type: VARCHAR
        description: <Descrição>.
        tests:
          - not_null
          # unique: somente se empiricamente único no recorte — verificar após rodar
      - name: <col2>
        data_type: VARCHAR    # ou INTEGER / DOUBLE / DATE / TIMESTAMP / GEOMETRY
        description: <Descrição>.
      - name: area_ha_calc
        data_type: DOUBLE
        description: >-
          Área em hectares computada pelo sistema a partir da geometria, via
          reprojeção equal-area EPSG:5880 (macro area_ha). Sufixo _calc marca campo
          gerado — distinto de area_ha, que vem da fonte.
        tests:
          - dbt_utils.accepted_range:
              min_value: 0
              inclusive: false
      - name: geometry
        data_type: GEOMETRY
        description: Geometria MULTIPOLYGON em EPSG:4326.
        tests:
          - not_null
```

**Nota sobre `unique`:** declarar somente se a coluna for empiricamente única **no recorte** do export.
Um recorte por UFs pode eliminar as duplicatas que existiam no staging completo — verificar após rodar.

---

## Verificação

```bash
# Rodar apenas o export (staging já deve estar populado)
uv run terrasync transform --select <model_name>

# Confirmar saída
ls "data/exports/<client>/<model_name>/"
# Esperado: v=YYYY-MM-DD/<model_name>.parquet

# Verificar shape e colunas
python -c "
import pyarrow.parquet as pq
import glob
f = glob.glob('data/exports/<client>/<model_name>/**/*.parquet', recursive=True)[0]
print(pq.read_schema(f))
print(pq.read_table(f).shape)
"
```

---

## Patterns comuns

| Padrão | Quando usar | Exemplo |
|--------|-------------|---------|
| **Dataset completo** | Fonte inteira sem filtro | `sigmine_opi` (Brasil inteiro) |
| **Recorte geográfico por UF** | Cliente com escopo regional | `sicar_opi` (11 UFs) |
| **Recorte temporal** | Janela de dados (alertas, eventos) | `WHERE data >= '2020-01-01'` |
| **Dedup por PK** | Staging tem duplicatas por design | `sicar_opi` (cod_imovel) |
| **Join com referência** | Enriquecer com tabela de domínio | `JOIN {{ ref('dim_municipios') }}` |

---

## Gotchas conhecidos

1. **Diretório de saída não existe — `_ensure_external_dirs`**
   O CLI `terrasync transform` pré-cria os diretórios de export via `_ensure_external_dirs` em `main.py`.
   Isso depende do `dbt ls` resolver o model. Se rodar `dbt run` diretamente (sem o CLI), criar o
   diretório manualmente ou usar o CLI.

2. **`unique` no recorte vs no staging**
   O staging pode ter duplicatas que somem após o filtro do export (ex.: UF não inclui os registros
   duplicados). Rodar o export e verificar antes de declarar `unique`.

3. **`export_path` gera path com `v=YYYY-MM-DD`**
   A versão é `run_started_at - 3h` (UTC-3) por default. Para fixar versão num run específico,
   passar `--vars '{"<client>_data_version": "2026-05-22"}'` no dbt. O CLI não expõe esse flag
   diretamente; usar `cd apps/dbt && uv run dbt run --vars '...'` nesse caso.

4. **Colunas do staging que mudam de tipo**
   Se o staging for re-rodado com `--full-refresh` e algum tipo mudar, o export pode falhar
   com type mismatch. Verificar schema do staging antes de declarar tipos no export YML.
