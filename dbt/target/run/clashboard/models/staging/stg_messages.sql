
  
  create view "clashboard"."main"."stg_messages__dbt_tmp" as (
    select * from read_parquet('az://silver/messages/*/*.parquet', hive_partitioning = true)
  );
