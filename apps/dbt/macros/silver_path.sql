{% macro silver_path(model_name) %}
    {{- return(var('data_root') ~ '/silver/' ~ model_name ~ '.parquet') -}}
{% endmacro %}
