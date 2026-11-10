
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  
    
    

with all_values as (

    select
        command_family as value_field,
        count(*) as n_records

    from "clashboard"."main"."bash_command_log"
    group by command_family

)

select *
from all_values
where value_field not in (
    'version control','search & read','files & archives','build & packages','run & test','shell','network','containers & cloud','data','dev tools','project scripts','other'
)



  
  
      
    ) dbt_internal_test