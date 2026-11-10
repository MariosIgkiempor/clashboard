select abs((select sum(cost_usd) from {{ ref('session_summary') }})
         - (select sum(cost_usd) from {{ ref('cost') }})) as diff
where diff > 0.01
