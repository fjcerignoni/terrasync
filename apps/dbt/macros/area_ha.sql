{% macro area_ha(geom_col='geometry', source_epsg=4326) %}
  ST_Area(ST_Transform({{ geom_col }}, 'EPSG:{{ source_epsg }}', 'EPSG:5880', always_xy := true)) / 10000.0
{% endmacro %}
