-- One row per event in a session, for the timeline drill-down: each assistant message (API call)
-- and each tool call. Tool calls link to their message via message_id; Bash rows carry the
-- redacted command preview. No prompt/response text is stored.
with messages as (
    select session_id, machine, project_name, ts,
           'message'                                            as event_type,
           message_id,
           message_id                                           as event_id,
           is_sidechain,
           model                                                as label,
           null::timestamptz                                    as end_ts,
           null::boolean                                        as is_error,
           input_tokens + cache_read_tokens + cache_write_tokens as context_tokens,
           output_tokens,
           cost_usd,
           null::bigint                                         as output_bytes,
           null::varchar                                        as detail
    from {{ ref('int_message_costs') }}
),
tools as (
    select t.session_id, t.machine, regexp_replace(t.project, '^-Users-[^-]+-', '') as project_name,
           t.ts,
           'tool'                 as event_type,
           t.message_id,
           t.tool_use_id          as event_id,
           t.is_sidechain,
           t.tool_name            as label,
           t.result_ts            as end_ts,
           t.is_error,
           null::bigint           as context_tokens,
           null::bigint           as output_tokens,
           null::double           as cost_usd,
           t.output_bytes,
           b.command_preview      as detail
    from {{ ref('stg_tool_calls') }} t
    left join {{ ref('bash_command_log') }} b using (tool_use_id)
)
select *,
       row_number() over (partition by session_id order by ts, event_type desc, event_id) as seq
from (select * from messages union all select * from tools)
