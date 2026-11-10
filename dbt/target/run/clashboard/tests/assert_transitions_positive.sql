
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select * from "clashboard"."main"."tool_transitions" where n <= 0 or from_tool is null or to_tool is null
  
  
      
    ) dbt_internal_test