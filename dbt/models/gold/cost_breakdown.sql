-- Where the money goes: cost by token type, per day and model.
select day, machine, model,
       sum(input_cost)       as input_cost,
       sum(output_cost)      as output_cost,
       sum(cache_read_cost)  as cache_read_cost,
       sum(cache_write_cost) as cache_write_cost,
       sum(cost_usd)         as total_cost
from {{ ref('int_message_costs') }}
group by all
