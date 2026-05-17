{{ config(
    materialized='external',
    location=staging_path('stg_incra_snci')
) }}

-- Une incra_snci_privado.parquet (51K rows) e incra_snci_publico.parquet (2K).
-- Schemas idênticos — union_by_name desnecessário.
-- tipo é derivado do filename (não existe na fonte).

{% set snci_source %}
SELECT
    regexp_extract(filename, 'incra_snci_(\w+)\.parquet', 1) AS tipo,
    num_proces,
    sr,
    num_certif,
    data_certi,
    qtd_area_p,
    cod_profis,
    cod_imovel,
    nome_imove,
    uf_municip,
    geometry
FROM read_parquet('{{ bronze_path("incra", glob="incra_snci_*.parquet") }}', filename = true)
{% endset %}

{{ clean_geometry(relation=snci_source, source_epsg=4674) }}
