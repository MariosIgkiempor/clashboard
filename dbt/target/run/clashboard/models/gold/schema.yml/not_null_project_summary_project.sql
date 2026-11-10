
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select project
from "clashboard"."main"."project_summary"
where project is null



  
  
      
    ) dbt_internal_test