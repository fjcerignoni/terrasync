{{ config(
    materialized='external',
    location=staging_path('stg_incra_snci')
) }}

-- Une incra_snci_privado.parquet e incra_snci_publico.parquet.
-- tipo derivado do filename (nao existe na fonte).

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
FROM read_parquet('{{ rawdata_path("incra_snci") }}', filename = true)
{% endset %}

{{ clean_geometry(relation=snci_source, source_epsg=4674) }}
