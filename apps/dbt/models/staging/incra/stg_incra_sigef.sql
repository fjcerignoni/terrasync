{{ config(
    materialized='external',
    location=staging_path('stg_incra_sigef')
) }}

-- Une incra_sigef_privado.parquet e incra_sigef_publico.parquet.
-- tipo derivado do filename (nao existe na fonte).

{% set sigef_source %}
SELECT
    regexp_extract(filename, 'incra_sigef_(\w+)\.parquet', 1) AS tipo,
    parcela_co,
    rt,
    art,
    situacao_i,
    codigo_imo,
    data_submi,
    data_aprov,
    status,
    nome_area,
    registro_m,
    registro_d,
    municipio_,
    uf_id,
    geometry
FROM {{ source('rawdata_incra', 'incra_sigef') }}
{% endset %}

{{ clean_geometry(relation=sigef_source, source_epsg=4674) }}
