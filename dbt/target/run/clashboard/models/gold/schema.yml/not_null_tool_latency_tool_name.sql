
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select tool_name
from "clashboard"."main"."tool_latency"
where tool_name is null



  
  
      
    ) dbt_internal_test