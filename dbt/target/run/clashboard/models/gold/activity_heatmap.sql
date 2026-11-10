
    

    create  table
      "clashboard"."main"."activity_heatmap__dbt_tmp"
  
    
    as (
      -- When do you work? Main-conversation messages by weekday and hour (display timezone).
with t as (
    select machine,
           timezone('Europe/London', ts) as local_ts,
           output_tokens
    from "clashboard"."main"."int_message_costs"
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
    );
    
  