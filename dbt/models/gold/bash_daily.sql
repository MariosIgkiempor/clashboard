select day,
       machine,
       command_family,
       command_head,
       count(*)                         as calls,
       count(*) filter (where is_error) as errors
from {{ ref('int_bash_commands') }}
group by all
