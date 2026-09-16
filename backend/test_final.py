"""测试清理后的父子分段检索"""
import asyncio
import json
from sqlalchemy import text
from app.db.session import async_session
from app.services.retrieval_test_service import start_run, execute_run


async def test_after_cleanup():
    test_set_id = '0094586d-0cbd-418f-86db-04e78f3c59d6'
    user_id = '0102ea2f-16cb-4029-b863-3807c213f148'

    print(f'测试集 ID: {test_set_id}')
    print(f'用户 ID: {user_id}')

    try:
        # 创建测试运行（不使用元数据过滤）
        run = await start_run(
            test_set_id=test_set_id,
            user_id=user_id,
            ks=[3, 5],
            override_config={'mode': 'parent_child'},
            document_metadata=None,
            chunk_metadata=None,
        )

        if hasattr(run, '_newly_created') and run._newly_created:
            print(f'\n创建新的测试运行: {run.id}')
            print('开始执行...')

            # 执行测试
            await execute_run(str(run.id))

            # 查询结果
            async with async_session() as session:
                result = await session.execute(
                    text('''
                        SELECT query, status, results
                        FROM retrieval_test_case_results
                        WHERE run_id = :id
                    '''),
                    {'id': str(run.id)}
                )
                cases = result.mappings().all()

                print(f'\n测试结果:')
                for i, case in enumerate(cases, 1):
                    print(f'\n用例 {i}:')
                    print(f'  查询: {case["query"]}')
                    print(f'  状态: {case["status"]}')

                    if case['results']:
                        print(f'  召回结果数量: {len(case["results"])}')
                        for j, r in enumerate(case['results'][:3], 1):
                            print(f'  结果 {j}:')
                            print(f'    父分段 ID: {r.get("id")}')
                            print(f'    标题: {r.get("title")}')
                            print(f'    内容长度: {len(r.get("content", ""))}')
                            print(f'    score: {r.get("score")}')
                            print(f'    children 数量: {len(r.get("children", []))}')

                            if '投标人须知' in r.get('title', ''):
                                print(f'    >>> 找到\"投标人须知\"章节！')
        else:
            print(f'测试运行已存在: {run.id}')

    except Exception as e:
        print(f'错误: {e}')
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(test_after_cleanup())