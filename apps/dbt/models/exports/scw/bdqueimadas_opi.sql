{{ config(
    materialized='external',
    location=export_path('scw', 'bdqueimadas_opi')
) }}

-- Export do cliente scw / projeto opi.
-- Focos de calor BDQueimadas (INPE) — cobertura nacional, sem recorte temático.
-- Geometria POINT validada em EPSG:4326.

select
    data_hora,
    satelite,
    estado,
    municipio,
    bioma,
    dia_sem_chuva,
    precipitacao,
    risco_fogo,
    frp,
    geometry
from {{ ref('slv_inpe_bdqueimadas') }}
