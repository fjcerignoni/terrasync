{% macro bronze_path(source, glob='*.parquet') %}
    {{- return(var('data_root') ~ '/bronze/' ~ source ~ '/' ~ glob) -}}
{% endmacro %}
