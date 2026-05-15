{{ config(
    materialized='external',
    location=staging_path('stg_incra_snci_publico')
) }}

{{ clean_geometry(bronze_path('incra_snci_publico'), source_epsg=4674) }}
