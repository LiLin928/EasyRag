"""Celery Worker 启动入口

使用方法:
    # 启动所有队列
    python celery_worker_main.py
    
    # 启动指定队列
    python celery_worker_main.py -Q parse
    
    # 指定并发数
    python celery_worker_main.py -c 8
"""
import os
import sys
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.celery_app import celery_app


def main():
    """启动 Celery Worker"""
    parser = argparse.ArgumentParser(description="EasyRAG Celery Worker")
    parser.add_argument(
        "-Q", "--queues",
        default="default,parse,workflow,agent",
        help="要监听的队列，逗号分隔 (默认: default,parse,workflow,agent)"
    )
    parser.add_argument(
        "-c", "--concurrency",
        type=int,
        default=4,
        help="并发 worker 数 (默认: 4)"
    )
    parser.add_argument(
        "-l", "--loglevel",
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="日志级别 (默认: info)"
    )
    parser.add_argument(
        "-n", "--hostname",
        default=None,
        help="Worker 主机名 (默认: auto)"
    )
    
    args = parser.parse_args()
    
    # 设置环境变量
    os.environ.setdefault("CELERY_WORKER_QUEUES", args.queues)
    
    # 构建 celery 参数
    celery_args = [
        "worker",
        "-Q", args.queues,
        "-c", str(args.concurrency),
        "-l", args.loglevel,
    ]
    
    if args.hostname:
        celery_args.extend(["-n", args.hostname])
    
    # 启动 worker
    print(f"Starting Celery Worker...")
    print(f"  Queues: {args.queues}")
    print(f"  Concurrency: {args.concurrency}")
    print(f"  Log Level: {args.loglevel}")
    
    try:
        celery_app.worker_main(celery_args)
    except KeyboardInterrupt:
        print("\nWorker stopped by user")
        sys.exit(0)


if __name__ == "__main__":
    main()
