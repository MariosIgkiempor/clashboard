
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

select
    project as unique_field,
    count(*) as n_records

from "clashboard"."main"."project_summary"
where project is not null
group by project
having count(*) > 1



  
  
      
    ) dbt_internal_test