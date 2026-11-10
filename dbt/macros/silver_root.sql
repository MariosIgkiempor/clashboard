{# Where silver Parquet lives. STORAGE_MODE=azurite reads from Azurite; anything else reads local files. #}
{% macro silver_root() -%}
{%- if env_var('STORAGE_MODE', 'local') == 'azurite' -%}az://silver{%- else -%}../data/silver{%- endif -%}
{%- endmacro %}
