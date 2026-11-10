
  
  create view "clashboard"."main"."stg_tool_calls__dbt_tmp" as (
    select * from read_parquet('az://silver/tool_calls/*/*.parquet', hive_partitioning = true)
  );
