-- One row per Bash tool call: what was run, with secrets redacted BEFORE anything is stored.
-- Result fields (is_error, output_bytes, latency_ms) are joined in dbt from silver tool_calls.
-- Stored text is truncated to 500 chars; the redaction is best-effort, not a guarantee.
CREATE OR REPLACE TEMP MACRO redact(s) AS
  regexp_replace(
  regexp_replace(
  regexp_replace(
  regexp_replace(
  regexp_replace(s,
    $$(?i)(authorization:\s*(?:bearer|basic)\s+)[^\s"']+$$, '\1[REDACTED]', 'g'),
    $$(?i)(--?(?:token|password|passwd|secret|api-?key|access-?key|key|auth)[ =])("[^"]*"|'[^']*'|\S+)$$, '\1[REDACTED]', 'g'),
    $$(?i)([A-Za-z0-9_]*(?:token|secret|passw(?:or)?d|key|credential|auth)[A-Za-z0-9_]*\s*[=:]\s*)("[^"]*"|'[^']*'|[^\s;&|]+)$$, '\1[REDACTED]', 'g'),
    $$://[^/\s:@]+:[^/\s@]+@$$, '://[REDACTED]@', 'g'),
    $$(?:sk-[A-Za-z0-9_-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}|[A-Za-z0-9+/]{64,}={0,2})$$, '[REDACTED]', 'g');

COPY (
  WITH rows AS (
    SELECT timestamp AS ts,
           sessionId AS session_id,
           isSidechain AS is_sidechain,
           regexp_extract(filename, 'bronze/(?:remote/[^/]+/)?([^/]+)/', 1) AS project,
           coalesce(nullif(regexp_extract(filename, 'bronze/remote/([^/]+)/', 1), ''), 'local') AS machine,
           from_json(
             CASE WHEN json_type(message.content) = 'ARRAY' THEN message.content ELSE '[]' END,
             '["JSON"]') AS items
    FROM read_json('{{bronze}}/**/*.jsonl',
      format='newline_delimited', ignore_errors=true, filename=true,
      columns={
        type:'VARCHAR', timestamp:'TIMESTAMPTZ', sessionId:'VARCHAR', isSidechain:'BOOLEAN',
        message:'STRUCT(id VARCHAR, content JSON)'
      })
    WHERE type = 'assistant'
  ),
  calls AS (
    SELECT ts, session_id, is_sidechain, project, machine,
           json_extract_string(i, '$.id')                        AS tool_use_id,
           json_extract_string(i, '$.input.command')             AS command,
           json_extract_string(i, '$.input.description')         AS description,
           json_extract(i, '$.input.timeout')::BIGINT            AS timeout_ms,
           coalesce(json_extract(i, '$.input.run_in_background')::BOOLEAN, false)        AS run_in_background,
           coalesce(json_extract(i, '$.input.dangerouslyDisableSandbox')::BOOLEAN, false) AS sandbox_disabled
    FROM (SELECT *, unnest(items) AS i FROM rows)
    WHERE json_extract_string(i, '$.type') = 'tool_use' AND json_extract_string(i, '$.name') = 'Bash'
  )
  SELECT DISTINCT ON (tool_use_id)
         tool_use_id, session_id, project, machine, is_sidechain, ts, ts::DATE AS day,
         left(redact(command), 500)                          AS command_redacted,
         length(command)                                     AS command_length,
         length(command) - length(replace(command, chr(10), '')) + 1 AS command_lines,
         left(redact(description), 200)                      AS description,
         timeout_ms, run_in_background, sandbox_disabled
  FROM calls
  WHERE command IS NOT NULL
  ORDER BY tool_use_id, ts
) TO '{{silver}}/bash_commands' (FORMAT parquet, PARTITION_BY (day));
