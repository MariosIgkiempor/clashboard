COPY (
  SELECT DISTINCT ON (message.id)
    message.id                              AS message_id,
    sessionId                               AS session_id,
    regexp_extract(filename, 'bronze/(?:remote/[^/]+/)?([^/]+)/', 1) AS project,
    coalesce(nullif(regexp_extract(filename, 'bronze/remote/([^/]+)/', 1), ''), 'local') AS machine,
    timestamp                               AS ts,
    timestamp::DATE                         AS day,
    message.model                           AS model,
    isSidechain                             AS is_sidechain,
    message.usage.input_tokens              AS input_tokens,
    message.usage.output_tokens             AS output_tokens,
    message.usage.cache_read_input_tokens   AS cache_read_tokens,
    message.usage.cache_creation_input_tokens AS cache_write_tokens
  FROM read_json('{{bronze}}/**/*.jsonl',
    format='newline_delimited', ignore_errors=true, filename=true,
    columns={
      type:'VARCHAR', timestamp:'TIMESTAMPTZ', sessionId:'VARCHAR', isSidechain:'BOOLEAN',
      message:'STRUCT(id VARCHAR, model VARCHAR, usage STRUCT(input_tokens BIGINT, output_tokens BIGINT, cache_read_input_tokens BIGINT, cache_creation_input_tokens BIGINT))'
    })
  WHERE type = 'assistant' AND message.id IS NOT NULL AND message.model <> '<synthetic>'
  ORDER BY message.id, timestamp
) TO '{{silver}}/messages' (FORMAT parquet, PARTITION_BY (day));
