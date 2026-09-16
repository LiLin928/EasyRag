"""执行技能插入脚本"""
import asyncio
import asyncpg

async def insert_skill():
    # 连接数据库
    conn = await asyncpg.connect(
        host="192.168.137.13",
        port=5432,
        user="easyrag",
        password="easyrag2026",
        database="easyrag_v2"
    )

    try:
        # 读取 SQL 文件
        with open("insert_skill_add_numbers.sql", "r", encoding="utf-8") as f:
            sql = f.read()

        # 执行插入
        await conn.execute(sql)

        print("✅ 技能插入成功！")

        # 查询验证
        row = await conn.fetchrow("""
            SELECT id, icon, name, scope, version,
                   jsonb_array_length(examples) as example_count,
                   jsonb_array_length(scripts) as script_count
            FROM skills
            WHERE name = '数字相加计算'
        """)

        print("\n插入的技能信息：")
        print(f"  ID: {row['id']}")
        print(f"  图标: {row['icon']}")
        print(f"  名称: {row['name']}")
        print(f"  范围: {row['scope']}")
        print(f"  版本: {row['version']}")
        print(f"  示例数: {row['example_count']}")
        print(f"  脚本数: {row['script_count']}")

    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(insert_skill())