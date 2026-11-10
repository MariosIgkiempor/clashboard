-- One row per tool call with a valid latency. Quantiles can't be merged across machines,
-- so the dashboard computes p50/p95 from these rows for whichever machines are selected.
-- Latency includes time you spent approving the call, so slow tools are often "waiting for a human".
select machine,
       tool_name,
       latency_ms
from {{ ref('stg_tool_calls') }}
where latency_ms is not null and latency_ms >= 0
