
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  select abs((select sum(cost_usd) from "clashboard"."main"."session_summary")
         - (select sum(cost_usd) from "clashboard"."main"."cost")) as diff
where diff > 0.01
  
  
      
    ) dbt_internal_test