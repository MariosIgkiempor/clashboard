
    

    create  table
      "clashboard"."main"."session_tools__dbt_tmp"
  
    
    as (
      select session_id,
       machine,
       tool_name,
       count(*)                         as calls,
       count(*) filter (where is_error) as errors,
       sum(output_bytes)                as output_bytes
from "clashboard"."main"."stg_tool_calls"
group by all
    );
    
  