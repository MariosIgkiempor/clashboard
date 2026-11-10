
    

    create  table
      "clashboard"."main"."bash_command_stats__dbt_tmp"
  
    
    as (
      -- Drill-down grain: family > head (program) > subcommand.
select machine,
       command_family,
       command_head,
       coalesce(command_subcommand, '(none)')                      as command_subcommand,
       count(*)                                                    as calls,
       count(*) filter (where is_error)                            as errors,
       100.0 * count(*) filter (where is_error) / count(*)         as error_pct,
       count(distinct session_id)                                  as sessions,
       count(distinct project)                                     as projects,
       min(day)                                                    as first_day,
       max(day)                                                    as last_day,
       sum(output_bytes)                                           as output_bytes,
       avg(output_bytes)                                           as avg_output_bytes,
       quantile_cont(latency_ms, 0.5)  / 1000.0                    as p50_seconds,
       quantile_cont(latency_ms, 0.95) / 1000.0                    as p95_seconds,
       avg(uses_pipe::int)                                         as pipe_share,
       avg(command_length)                                         as avg_command_length,
       count(*) filter (where run_in_background)                   as background_calls
from "clashboard"."main"."int_bash_commands"
group by all
    );
    
  