
  
  create view "clashboard"."main"."stg_bash_commands__dbt_tmp" as (
    select * from read_parquet('az://silver/bash_commands/*/*.parquet', hive_partitioning = true)
  );
