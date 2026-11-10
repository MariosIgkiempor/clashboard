
    
    

select
    tool_use_id as unique_field,
    count(*) as n_records

from "clashboard"."main"."bash_command_log"
where tool_use_id is not null
group by tool_use_id
having count(*) > 1


