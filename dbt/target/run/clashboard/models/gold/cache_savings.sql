
    

    create  table
      "clashboard"."main"."cache_savings__dbt_tmp"
  
    
    as (
      -- What prompt caching saved: actual cost vs the same tokens at the plain input price.
select day, machine, model,
       sum(cost_usd)                         as actual_cost,
       sum(cost_usd_no_cache)                as cost_without_cache,
       sum(cost_usd_no_cache) - sum(cost_usd) as savings_usd
from "clashboard"."main"."int_message_costs"
group by all
    );
    
  