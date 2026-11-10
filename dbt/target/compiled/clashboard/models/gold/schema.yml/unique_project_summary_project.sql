
    
    

select
    project as unique_field,
    count(*) as n_records

from "clashboard"."main"."project_summary"
where project is not null
group by project
having count(*) > 1


