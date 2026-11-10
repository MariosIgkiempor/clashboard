
    
    select
      count(*) as failures,
      count(*) != 0 as should_warn,
      count(*) != 0 as should_error
    from (
      
    
  -- Every Bash tool call must have exactly one parsed command row (and vice versa).
select (select count(*) from "clashboard"."main"."stg_tool_calls" where tool_name = 'Bash') as tool_calls_bash,
       (select count(*) from "clashboard"."main"."int_bash_commands")                      as parsed_commands
where tool_calls_bash <> parsed_commands
  
  
      
    ) dbt_internal_test