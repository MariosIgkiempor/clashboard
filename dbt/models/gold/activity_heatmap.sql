-- When do you work? Main-conversation messages by weekday and hour (display timezone).
with t as (
    select machine,
           timezone('{{ var("display_timezone", env_var("TIMEZONE", "UTC")) }}', ts) as local_ts,
           output_tokens
    from {{ ref('int_message_costs') }}
    where not is_sidechain
)
select machine,
       isodow(local_ts)  as weekday_num,
       dayname(local_ts) as weekday,
       hour(local_ts)    as hour,
       count(*)          as messages,
       sum(output_tokens) as output_tokens
from t
group by all
