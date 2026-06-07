{{ config(
    materialized='external',
    location=bronze_path('prodes', 'cerrado'),
    tags=['bronze']
) }}

with cleaned as (
    {{
        clean_geometry(
            rawdata_path('prodes', glob='prodes_cerrado.parquet'),
            source_epsg=4674,
            id_columns=['uid'],
            dedup_id=['uid'],
            dedup_date='image_date'
        )
    }}
)
select
    stg_id,
    {{ dbt_utils.generate_surrogate_key(['uid']) }} as uuid,
    * exclude (stg_id, uid),
    'cerrado' as biome
from cleaned