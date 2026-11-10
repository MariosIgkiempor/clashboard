-- Which tool tends to follow which (window function over each session's call order).
with labelled as (
    select machine, session_id, is_sidechain, ts, tool_use_id,
           case when starts_with(tool_name, 'mcp__') then 'mcp:' || split_part(tool_name, '__', 3)
                else tool_name end as tool_label
    from {{ ref('stg_tool_calls') }}
),
ordered as (
    select machine, tool_label as from_tool,
           lead(tool_label) over (partition by session_id, is_sidechain order by ts, tool_use_id) as to_tool
    from labelled
)
select machine, from_tool, to_tool, count(*) as n
from ordered
where to_tool is not null
group by all
