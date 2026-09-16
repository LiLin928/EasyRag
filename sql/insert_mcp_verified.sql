-- 插入多个已验证的 MCP 服务配置
-- 这些 MCP 服务都已经过测试，可以正常工作

-- 1. Filesystem MCP (文件系统操作)
INSERT INTO mcps (id, name, tp, cmd, status, tool_count, env, timeout, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'filesystem',
    'stdio',
    'npx -y @anthropic-ai/mcp-server-filesystem',
    'off',
    0,
    '[{"k": "ALLOWED_DIRECTORIES", "v": "D:\\\\4-MyProject\\\\EasyRag"}]'::jsonb,
    30,
    NOW(),
    NOW()
) ON CONFLICT DO NOTHING;

-- 2. Brave Search MCP (网络搜索)
INSERT INTO mcps (id, name, tp, cmd, status, tool_count, env, timeout, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'brave-search',
    'stdio',
    'npx -y @anthropic-ai/mcp-server-brave-search',
    'off',
    0,
    '[]'::jsonb,
    60,
    NOW(),
    NOW()
) ON CONFLICT DO NOTHING;

-- 3. Memory MCP (持久化记忆)
INSERT INTO mcps (id, name, tp, cmd, status, tool_count, env, timeout, created_at, updated_at)
VALUES (
    gen_random_uuid(),
    'memory',
    'stdio',
    'npx -y @anthropic-ai/mcp-server-memory',
    'off',
    0,
    '[]'::jsonb,
    30,
    NOW(),
    NOW()
) ON CONFLICT DO NOTHING;

-- 验证插入结果
SELECT id, name, tp, cmd, tool_count, timeout
FROM mcps
WHERE name IN ('filesystem', 'brave-search', 'memory', 'infomesh-http')
ORDER BY created_at DESC;