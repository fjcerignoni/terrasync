{{ config(
    materialized='external',
    location=bronze_path('sicar', 'ma'),
    tags=['bronze']
) }}

{{
    clean_geometry(
        rawdata_path('sicar', glob='sicar_ma.parquet'),
        source_epsg=4674,
        id_columns=['cod_imovel'],
        dedup_id=['cod_imovel'],
        dedup_date='dat_criacao'
    )
}}