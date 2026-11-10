select day,
       machine,
       mcp_server,
       mcp_tool,
       count(*)                                   as calls,
       count(*) filter (where is_error)           as errors,
       sum(output_bytes)                          as output_bytes
from "clashboard"."main"."stg_tool_calls"
where mcp_server is not null
group by all