
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    



select calls
from "clashboard"."main"."bash_command_stats"
where calls is null



  
  
      
    ) dbt_internal_test