
    
    

with child as (
    select tool_use_id as from_field
    from "clashboard"."main"."bash_command_log"
    where tool_use_id is not null
),

parent as (
    select tool_use_id as to_field
    from "clashboard"."main"."stg_tool_calls"
)

select
    from_field

from child
left join parent
    on child.from_field = parent.to_field

where parent.to_field is null


