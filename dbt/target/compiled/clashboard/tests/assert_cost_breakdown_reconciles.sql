-- Singular test: returns rows (= fails) if the token-type breakdown does not add up to the cost model.
select abs((select sum(total_cost) from "clashboard"."main"."cost_breakdown")
         - (select sum(cost_usd)  from "clashboard"."main"."cost")) as diff
where diff > 0.01