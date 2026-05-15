{{ config(
    materialized='external',
    location=staging_path('stg_incra_snci_privado')
) }}

{{ clean_geometry(bronze_path('incra_snci_privado'), source_epsg=4674) }}
