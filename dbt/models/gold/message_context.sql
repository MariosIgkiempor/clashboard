-- Context size at every API call (input + cache read + cache write). Shows context growth,
-- compaction drops, and subagent spin-ups inside a session.
select session_id,
       machine,
       project,
       ts,
       row_number() over (partition by session_id, is_sidechain order by ts, message_id) as message_index,
       is_sidechain,
       model,
       input_tokens + cache_read_tokens + cache_write_tokens as context_tokens,
       output_tokens
from {{ ref('int_message_costs') }}
