
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select tool_use_id
from "clashboard"."main"."stg_tool_calls"
where tool_use_id is null



  
  
      
    ) dbt_internal_test