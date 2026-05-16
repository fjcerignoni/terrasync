{% macro export_path(client, model_name, version=none) %}
    {%- set v = version or var(client ~ '_data_version', run_started_at.strftime('%Y-%m-%d')) -%}
    {{- return(var('data_root') ~ '/exports/' ~ client ~ '/' ~ model_name ~ '/v=' ~ v ~ '/' ~ model_name ~ '.parquet') -}}
{% endmacro %}
