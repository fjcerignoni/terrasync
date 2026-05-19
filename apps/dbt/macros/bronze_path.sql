{% macro bronze_path(source, layer) %}
    {{- return(var('data_root') ~ '/bronze/' ~ source ~ '/' ~ source ~ '_' ~ layer ~ '.parquet') -}}
{% endmacro %}
