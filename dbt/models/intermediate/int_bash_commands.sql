-- Parse each Bash command into: head (the program), subcommand (git *status*, npm *run*), family,
-- plus shape flags. This is heuristic shell parsing in SQL: good enough for usage analytics,
-- not a real shell parser.
with stripped as (
    select *,
           -- remove leading "cd x &&", ENV=val, sudo/time/env prefixes, "set -e;", "export X=y &&", "(" and "{"
           regexp_replace(
               trim(command_redacted),
               $$^(?:(?:cd\s+(?:"[^"]*"|'[^']*'|\S+)\s*(?:&&|;)|[A-Za-z_][A-Za-z0-9_]*=(?:"[^"]*"|'[^']*'|[^\s;&]*)(?:\s*(?:&&|;))?|sudo|time|nohup|env|set\s+-\w+\s*;?|export\s+\w+=\S+\s*(?:&&|;)?|#[^\n]*(?:\n|$)|\(|\{)\s*)+$$,
               ''
           ) as core
    from {{ ref('stg_bash_commands') }}
),
parsed as (
    select *,
           regexp_extract(core, $$^[!"'`]*([^\s;|&<>()"'`]+)$$, 1)                       as raw_head
    from stripped
),
named as (
    select *,
           regexp_replace(raw_head, '^.*/', '')                                            as head_base
    from parsed
),
joined as (
    select n.*,
           f.command_family  as seed_family,
           coalesce(f.has_subcommand, false) as has_subcommand
    from named n
    left join {{ ref('command_families') }} f on f.command_head = n.head_base
)
select j.tool_use_id,
       j.session_id,
       j.project,
       j.machine,
       regexp_replace(j.project, '^-Users-[^-]+-', '')                                     as project_name,
       j.is_sidechain,
       j.ts,
       j.day,
       coalesce(nullif(j.head_base, ''), '(none)')                                         as command_head,
       case when j.has_subcommand
            then nullif(regexp_extract(j.core, $$^\S+\s+(?:-{1,2}[A-Za-z0-9_=-]+\s+)*([a-z][a-z0-9:_-]*)(?:\s|$)$$, 1), '')
       end                                                                                 as command_subcommand,
       case when j.seed_family is not null then j.seed_family
            when j.raw_head like './%' or j.raw_head like '../%' or j.raw_head like '%.sh' then 'project scripts'
            else 'other' end                                                               as command_family,
       j.description,
       left(j.command_redacted, 300)                                                       as command_preview,
       j.command_length,
       j.command_lines,
       len(regexp_extract_all(j.core, $$&&|\|\||;|\n$$)) + 1                               as n_segments,
       regexp_matches(j.core, $$[^|]\|[^|]$$)                                              as uses_pipe,
       contains(j.core, '<<')                                                              as has_heredoc,
       j.run_in_background,
       j.sandbox_disabled,
       j.timeout_ms,
       coalesce(t.is_error, false)                                                         as is_error,
       t.output_bytes,
       t.latency_ms
from joined j
left join {{ ref('stg_tool_calls') }} t using (tool_use_id)
