
    
    

with child as (
    select model as from_field
    from "clashboard"."main"."stg_messages"
    where model is not null
),

parent as (
    select model as to_field
    from "clashboard"."main"."prices"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


