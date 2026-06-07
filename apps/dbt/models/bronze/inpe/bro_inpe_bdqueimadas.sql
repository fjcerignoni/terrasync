{{ config(
    materialized='external',
    location=bronze_path('inpe', 'bdqueimadas'),
    tags=['bronze']
) }}

{% set source_rel %}
select
    strptime(cast(DataHora as varchar), '%Y/%m/%d %H:%M:%S') as data_hora,
    Satelite  as satelite,
    Estado    as estado,
    Municipio as municipio,
    Bioma     as bioma,
    cast(DiaSemChuva  as integer) as dia_sem_chuva,
    cast(Precipitacao as double)  as precipitacao,
    cast(RiscoFogo    as double)  as risco_fogo,
    cast(FRP          as double)  as frp,
    geometry
from {{ source('rawdata_inpe', 'inpe_bdqueimadas') }}
{% endset %}

{{
    clean_point_geometry(
        relation=source_rel,
        source_epsg=4326,
        id_columns=['data_hora', 'satelite', 'ST_AsText(geometry)']
    )
}}
