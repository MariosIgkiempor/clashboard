import dagster as dg

# Everything: bronze -> silver -> dbt -> gold export.
full_refresh = dg.define_asset_job("full_refresh", selection=dg.AssetSelection.all())
