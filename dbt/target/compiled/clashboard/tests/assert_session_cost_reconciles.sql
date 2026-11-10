select abs((select sum(cost_usd) from "clashboard"."main"."session_summary")
         - (select sum(cost_usd) from "clashboard"."main"."cost")) as diff
where diff > 0.01