
    

    create  table
      "clashboard"."main"."cost__dbt_tmp"
  
    
    as (
      select u.day, u.machine, u.model,
       u.input_tokens       / 1e6 * p.input_per_mtok
     + u.output_tokens      / 1e6 * p.output_per_mtok
     + u.cache_read_tokens  / 1e6 * p.cache_read_per_mtok
     + u.cache_write_tokens / 1e6 * p.cache_write_per_mtok as cost_usd
from "clashboard"."main"."daily_usage" u
left join "clashboard"."main"."prices" p using (model)
    );
    
  