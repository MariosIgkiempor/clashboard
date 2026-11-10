# Claude usage

```sql spend
select day, model, cost_usd from clashboard.cost order by day
```

<BarChart data={spend} x=day y=cost_usd series=model title="Estimated cost per day (USD)" />

<DataTable data={spend} />
