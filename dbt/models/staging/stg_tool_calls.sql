select * from {{ source('silver', 'tool_calls') }}
