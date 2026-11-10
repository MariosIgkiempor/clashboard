-- Additive daily totals per machine (active days only). The dashboard builds the gap-free
-- calendar spine and rolling windows over whichever machines are selected.
select day,
       machine,
       sum(cost_usd)               as cost_usd,
       count(*)                    as messages,
       sum(output_tokens)          as output_tokens,
       count(distinct session_id)  as sessions,
       count(distinct project)     as projects
from "clashboard"."main"."int_message_costs"
group by day, machine