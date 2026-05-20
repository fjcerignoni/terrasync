{% macro export_path(client, model_name, version=none) %}
    {%- set _ts = run_started_at - modules.datetime.timedelta(hours=3) -%}
    {%- set v = version or var(client ~ '_data_version', _ts.strftime('%Y-%m-%d')) -%}
    {{- return(var('data_root') ~ '/exports/' ~ client ~ '/' ~ model_name ~ '/v=' ~ v ~ '/' ~ model_name ~ '.parquet') -}}
{% endmacro %}
