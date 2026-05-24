{{ config(
    materialized='external',
    location=staging_path('stg_deter')
) }}

{% set deter_source %}
SELECT *, 'amazonia' AS biome FROM {{ source('rawdata_inpe', 'deter_amazonia') }}
UNION ALL BY NAME
SELECT *, 'cerrado' AS biome FROM {{ source('rawdata_inpe', 'deter_cerrado') }}
{% endset %}

{{ clean_geometry(relation=deter_source, source_epsg=4674) }}
