-- One row per tool call: the tool_use (assistant row) joined to its tool_result (user row).
-- Deduplicated on tool_use_id (resumed sessions copy history across files).
-- Input/output text is NOT stored (secrets); only sizes.
COPY (
  WITH rows AS (
    SELECT type,
           timestamp AS ts,
           sessionId AS session_id,
           isSidechain AS is_sidechain,
           regexp_extract(filename, 'bronze/(?:remote/[^/]+/)?([^/]+)/', 1) AS project,
           coalesce(nullif(regexp_extract(filename, 'bronze/remote/([^/]+)/', 1), ''), 'local') AS machine,
           message.id AS message_id,
           from_json(
             CASE WHEN json_type(message.content) = 'ARRAY' THEN message.content ELSE '[]' END,
             '["JSON"]') AS items
    FROM read_json('{{bronze}}/**/*.jsonl',
      format='newline_delimited', ignore_errors=true, filename=true,
      columns={
        type:'VARCHAR', timestamp:'TIMESTAMPTZ', sessionId:'VARCHAR', isSidechain:'BOOLEAN',
        message:'STRUCT(id VARCHAR, content JSON)'
      })
    WHERE type IN ('assistant', 'user')
  ),
  uses AS (
    SELECT DISTINCT ON (tool_use_id) *
    FROM (
      SELECT json_extract_string(i, '$.id')   AS tool_use_id,
             json_extract_string(i, '$.name') AS tool_name,
             message_id, session_id, project, machine, is_sidechain, ts,
             strlen(json_extract(i, '$.input')::VARCHAR) AS input_bytes
      FROM (SELECT *, unnest(items) AS i FROM rows WHERE type = 'assistant')
      WHERE json_extract_string(i, '$.type') = 'tool_use'
    )
    ORDER BY tool_use_id, ts
  ),
  results AS (
    SELECT DISTINCT ON (tool_use_id) *
    FROM (
      SELECT json_extract_string(i, '$.tool_use_id') AS tool_use_id,
             coalesce(json_extract(i, '$.is_error')::BOOLEAN, false) AS is_error,
             strlen(json_extract(i, '$.content')::VARCHAR) AS output_bytes,
             ts AS result_ts
      FROM (SELECT *, unnest(items) AS i FROM rows WHERE type = 'user')
      WHERE json_extract_string(i, '$.type') = 'tool_result'
    )
    ORDER BY tool_use_id, result_ts
  )
  SELECT u.tool_use_id,
         u.tool_name,
         CASE WHEN starts_with(u.tool_name, 'mcp__') THEN split_part(u.tool_name, '__', 2) END AS mcp_server,
         CASE WHEN starts_with(u.tool_name, 'mcp__') THEN split_part(u.tool_name, '__', 3) END AS mcp_tool,
         u.message_id, u.session_id, u.project, u.machine, u.is_sidechain,
         u.ts, u.ts::DATE AS day,
         u.input_bytes,
         r.is_error,
         r.output_bytes,
         r.result_ts,
         date_diff('millisecond', u.ts, r.result_ts) AS latency_ms
  FROM uses u
  LEFT JOIN results r USING (tool_use_id)
) TO '{{silver}}/tool_calls' (FORMAT parquet, PARTITION_BY (day));
