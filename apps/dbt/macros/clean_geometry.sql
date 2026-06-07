{% macro clean_geometry(parquet_path=none, source_epsg=4674, relation=none, id_columns=none, dedup_id=none, dedup_date=none) %}
with raw as (
    {% if relation is not none -%}
    {{ relation }}
    {%- else -%}
    select * from read_parquet('{{ parquet_path }}')
    {%- endif %}
),
{% if dedup_id is not none %}
deduped as (
    select * exclude (_rn)
    from (
        select
            *,
            row_number() over (
                partition by {{ dedup_id | join(', ') }}
                {% if dedup_date %}order by {{ dedup_date }} desc nulls last{% endif %}
            ) as _rn
        from raw
    )
    where _rn = 1
),
{% endif %}
flattened as (
    select
        * exclude (geometry),
        ST_Force2D(geometry) as geometry
    from {% if dedup_id is not none %}deduped{% else %}raw{% endif %}
    where geometry is not null
),
validated as (
    select
        * exclude (geometry),
        case
            when ST_IsValid(geometry) then ST_Multi(geometry)
            else ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_Buffer(geometry,0)), 3))
        end as geometry_valid
    from flattened
),
reprojected as (
    select
        * exclude (geometry_valid),
        {% if source_epsg == 4326 %}
        geometry_valid as geometry
        {% else %}
        ST_Transform(
            geometry_valid,
            'EPSG:{{ source_epsg }}',
            'EPSG:4326',
            always_xy := true
        ) as geometry
        {% endif %}
    from validated
)
select
    {% if id_columns is not none %}
    md5(concat_ws('|',
        {% for expr in id_columns %}
        cast({{ expr }} as varchar){% if not loop.last %},{% endif %}
        {% endfor %}
    )) as stg_id,
    {% else %}
    md5(ST_AsText(geometry)) as stg_id,
    {% endif %}
    * exclude (geometry),
    geometry
from reprojected
where geometry is not null
  and not ST_IsEmpty(geometry)
  and ST_XMin(geometry) >= -180
  and ST_YMin(geometry) >= -90
  and ST_XMax(geometry) <= 180
  and ST_YMax(geometry) <= 90
{% endmacro %}
