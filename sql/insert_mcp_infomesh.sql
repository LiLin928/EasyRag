-- 插入 MCP 服务：infomesh
-- infomesh 是一个信息检索 MCP 服务器

INSERT INTO mcps (
    id,
    name,
    tp,
    cmd,
    status,
    tool_count,
    env,
    timeout,
    created_at,
    updated_at
) VALUES (
    gen_random_uuid(),
    'infomesh',
    'stdio',
    'uvx infomesh mcp',
    'off',
    0,
    '[]'::jsonb,
    60,
    NOW(),
    NOW()
);

-- 验证插入结果
SELECT
    id,
    name,
    tp,
    cmd,
    status,
    tool_count,
    timeout
FROM mcps
WHERE name = 'infomesh';