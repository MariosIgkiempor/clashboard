
    
    

select
    day as unique_field,
    count(*) as n_records

from "clashboard"."main"."daily_trends"
where day is not null
group by day
having count(*) > 1


