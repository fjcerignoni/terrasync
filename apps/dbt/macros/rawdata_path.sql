{% macro rawdata_path(source, glob='*.parquet') %}
    {{- return(var('data_root') ~ '/rawdata/' ~ source ~ '/' ~ glob) -}}
{% endmacro %}
