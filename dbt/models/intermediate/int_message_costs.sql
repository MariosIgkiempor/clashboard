-- One row per assistant message, with its cost split by token type.
-- Reused by every model that needs cost below the daily/model grain.
select m.message_id,
       m.session_id,
       m.project,
       m.machine,
       regexp_replace(m.project, '^-Users-[^-]+-', '') as project_name,
       m.ts,
       m.day,
       m.model,
       m.is_sidechain,
       m.input_tokens,
       m.output_tokens,
       m.cache_read_tokens,
       m.cache_write_tokens,
       m.input_tokens       / 1e6 * p.input_per_mtok       as input_cost,
       m.output_tokens      / 1e6 * p.output_per_mtok      as output_cost,
       m.cache_read_tokens  / 1e6 * p.cache_read_per_mtok  as cache_read_cost,
       m.cache_write_tokens / 1e6 * p.cache_write_per_mtok as cache_write_cost,
       m.input_tokens       / 1e6 * p.input_per_mtok
         + m.output_tokens      / 1e6 * p.output_per_mtok
         + m.cache_read_tokens  / 1e6 * p.cache_read_per_mtok
         + m.cache_write_tokens / 1e6 * p.cache_write_per_mtok as cost_usd,
       -- what the same tokens would cost with no prompt caching at all
       (m.input_tokens + m.cache_read_tokens + m.cache_write_tokens) / 1e6 * p.input_per_mtok
         + m.output_tokens / 1e6 * p.output_per_mtok          as cost_usd_no_cache
from {{ ref('stg_messages') }} m
left join {{ ref('prices') }} p using (model)
