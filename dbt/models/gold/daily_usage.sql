select day, machine, model,
       count(*)                 as msgs,
       sum(input_tokens)        as input_tokens,
       sum(output_tokens)       as output_tokens,
       sum(cache_read_tokens)   as cache_read_tokens,
       sum(cache_write_tokens)  as cache_write_tokens
from {{ ref('stg_messages') }}
group by all
