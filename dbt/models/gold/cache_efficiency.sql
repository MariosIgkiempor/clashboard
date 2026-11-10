-- Share of all input-side tokens that were served from cache.
select day,
       machine,
       project,
       sum(cache_read_tokens)  as cache_read_tokens,
       sum(cache_write_tokens) as cache_write_tokens,
       sum(input_tokens)       as uncached_input_tokens,
       sum(cache_read_tokens)::double
         / nullif(sum(cache_read_tokens) + sum(cache_write_tokens) + sum(input_tokens), 0) as cache_hit_ratio
from {{ ref('stg_messages') }}
group by all
