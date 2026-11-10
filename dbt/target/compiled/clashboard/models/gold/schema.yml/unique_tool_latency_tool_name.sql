
    
    

select
    tool_name as unique_field,
    count(*) as n_records

from "clashboard"."main"."tool_latency"
where tool_name is not null
group by tool_name
having count(*) > 1


