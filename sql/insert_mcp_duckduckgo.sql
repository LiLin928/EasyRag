-- 插入 DuckDuckGo 搜索 MCP
-- DuckDuckGo 搜索服务，提供隐私保护的搜索功能

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
    'duckduckgo-search',
    'stdio',
    'uvx duckduckgo-mcp-server',
    'off',
    0,
    '[
        {"k": "DDG_REGION", "v": "cn-zh"},
        {"k": "DDG_SAFE_SEARCH", "v": "MODERATE"},
        {"k": "DDG_SEARCH_RPM", "v": "30"},
        {"k": "DDG_CACHE_TTL", "v": "300"}
    ]'::jsonb,
    60,
    NOW(),
    NOW()
);

-- 验证插入
SELECT
    id,
    name,
    tp,
    cmd,
    status,
    env,
    timeout
FROM mcps
WHERE name = 'duckduckgo-search';