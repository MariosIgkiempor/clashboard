with msg as (
    select session_id,
           any_value(project)                   as project,
           any_value(machine)                   as machine,
           any_value(project_name)              as project_name,
           min(ts)                              as started_at,
           max(ts)                              as ended_at,
           date_diff('minute', min(ts), max(ts)) as duration_min,
           count(*)                             as messages,
           count(*) filter (where is_sidechain) as subagent_messages,
           sum(output_tokens)                   as output_tokens,
           sum(cache_read_tokens)               as cache_read_tokens,
           sum(cost_usd)                        as cost_usd
    from {{ ref('int_message_costs') }}
    group by session_id
),
tools as (
    select session_id, count(*) as tool_calls, count(*) filter (where is_error) as tool_errors
    from {{ ref('stg_tool_calls') }}
    group by session_id
)
select msg.*,
       msg.cost_usd / nullif(msg.messages, 0)   as cost_per_message,
       coalesce(tools.tool_calls, 0)            as tool_calls,
       coalesce(tools.tool_errors, 0)           as tool_errors
from msg left join tools using (session_id)
