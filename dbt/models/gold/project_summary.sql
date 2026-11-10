with m as (
    select project, machine,
           any_value(project_name)               as project_name,
           count(distinct session_id)            as sessions,
           count(*)                              as messages,
           count(*) filter (where is_sidechain)  as subagent_messages,
           min(day)                              as first_day,
           max(day)                              as last_day,
           sum(cost_usd)                         as cost_usd,
           sum(cost_usd_no_cache)                as cost_without_cache,
           sum(output_tokens)                    as output_tokens,
           sum(cache_read_tokens)::double
             / nullif(sum(cache_read_tokens) + sum(cache_write_tokens) + sum(input_tokens), 0) as cache_hit_ratio
    from {{ ref('int_message_costs') }}
    group by project, machine
),
t as (
    select project, machine, count(*) as tool_calls, count(*) filter (where is_error) as tool_errors
    from {{ ref('stg_tool_calls') }}
    group by project, machine
)
select m.*, coalesce(t.tool_calls, 0) as tool_calls, coalesce(t.tool_errors, 0) as tool_errors,
       m.subagent_messages::double / nullif(m.messages, 0) as subagent_share
from m left join t using (project, machine)
