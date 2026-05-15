{% macro staging_path(model_name) %}
    {{- return(var('data_root') ~ '/staging/' ~ model_name ~ '.parquet') -}}
{% endmacro %}
