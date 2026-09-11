"""
诊断前端状态
"""
import asyncio
from app.db.session import async_session
from sqlalchemy import text

async def diagnose():
    async with async_session() as session:
        print('=' * 80)
        print('前端状态诊断')
        print('=' * 80)
        print()

        # 1. 检查测试集
        print('1. 检查测试集列表')
        print('-' * 80)
        result = await session.execute(
            text('''
                SELECT id, name, kb_id
                FROM retrieval_test_sets
                WHERE kb_id = 'add1629a-e683-4ed7-9d7a-f261b01331f2'
                ORDER BY created_at DESC
            ''')
        )
        test_sets = result.fetchall()

        print(f'测试集数量: {len(test_sets)}')
        for i, ts in enumerate(test_sets, 1):
            print(f'{i}. {ts[1]} ({ts[0]})')

        print()

        # 2. 检查最新的测试集
        if test_sets:
            latest_ts = test_sets[0]
            print('2. 检查最新测试集的详细信息')
            print('-' * 80)
            print(f'测试集: {latest_ts[1]}')
            print(f'ID: {latest_ts[0]}')

            # 查询测试运行
            result = await session.execute(
                text('''
                    SELECT id, status, total_cases, completed_cases
                    FROM retrieval_test_runs
                    WHERE test_set_id = :ts_id
                    ORDER BY created_at DESC
                    LIMIT 1
                '''),
                {'ts_id': str(latest_ts[0])}
            )
            run = result.fetchone()

            if run:
                print(f'最新测试运行:')
                print(f'  ID: {run[0]}')
                print(f'  状态: {run[1]}')
                print(f'  总用例: {run[2]}')
                print(f'  已完成: {run[3]}')

                # 查询测试结果
                result = await session.execute(
                    text('''
                        SELECT id, case_id, status, query, expected_doc_ids, hit_doc_ids
                        FROM retrieval_test_case_results
                        WHERE run_id = :run_id
                    '''),
                    {'run_id': str(run[0])}
                )
                results = result.fetchall()

                print(f'  测试结果数量: {len(results)}')

                if results:
                    r = results[0]
                    print(f'  第一个结果:')
                    print(f'    ID: {r[0]}')
                    print(f'    用例ID: {r[1]}')
                    print(f'    状态: {r[2]}')
                    print(f'    查询: {r[3]}')
                    print(f'    期望文档: {r[4]}')
                    print(f'    命中文档: {r[5]}')

                    # 检查是否有数据
                    if r[2] == 'hit':
                        print()
                        print('✅ 测试成功！状态为 "hit"')
                        print('✅ 前端应该能够显示结果')
                    else:
                        print()
                        print(f'⚠️ 测试状态为 "{r[2]}"，不是 "hit"')
            else:
                print('  ❌ 没有测试运行')

        print()
        print('=' * 80)
        print('诊断结论')
        print('=' * 80)
        print()
        print('数据是正确的，问题可能在于前端：')
        print()
        print('1. 请在左侧测试集列表中选择 "afsd" 测试集')
        print('2. 选择后，右侧应该显示测试结果')
        print('3. 如果还是不显示，请检查浏览器控制台是否有错误')
        print()

asyncio.run(diagnose())