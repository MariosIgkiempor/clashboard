-- Leaf level of the drill-down: every individual command (redacted preview, truncated).
select tool_use_id, session_id, machine, project_name, ts, day,
       command_family, command_head, coalesce(command_subcommand, '(none)') as command_subcommand,
       description, command_preview, command_length, command_lines, n_segments,
       uses_pipe, has_heredoc, run_in_background, sandbox_disabled,
       is_error, output_bytes, latency_ms
from {{ ref('int_bash_commands') }}
