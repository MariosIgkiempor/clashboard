-- Main conversation vs subagents.
select day,
       machine,
       case when is_sidechain then 'subagent' else 'main' end as agent_type,
       count(*)           as messages,
       sum(output_tokens) as output_tokens,
       sum(cost_usd)      as cost_usd
from {{ ref('int_message_costs') }}
group by all
