select * from {{ source('silver', 'bash_commands') }}
