
    

    create  table
      "clashboard"."main"."tool_stats__dbt_tmp"
  
    
    as (
      select day,
       machine,
       tool_name,
       count(*)                                   as calls,
       count(*) filter (where is_error)           as errors,
       sum(output_bytes)                          as output_bytes,
       round(avg(output_bytes))                   as avg_output_bytes,
       round(avg(latency_ms))                     as avg_latency_ms
from "clashboard"."main"."stg_tool_calls"
group by all
    );
    
  