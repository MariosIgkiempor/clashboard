select session_id,
       machine,
       tool_name,
       count(*)                         as calls,
       count(*) filter (where is_error) as errors,
       sum(output_bytes)                as output_bytes
from {{ ref('stg_tool_calls') }}
group by all
