#!/usr/bin/env python3
"""多 Worker 进程启动器。"""
import argparse
import subprocess
import sys
import time
from typing import List


def start_workers(count: int = 3, fast_interval: float = 0.1, slow_interval: float = 5.0) -> List[subprocess.Popen]:
    """启动多个 Worker 进程。
    
    Args:
        count: Worker 进程数量
        fast_interval: 有任务时轮询间隔（秒）
        slow_interval: 无任务时轮询间隔（秒）
        
    Returns:
        Worker 进程列表
    """
    procs = []
    
    for i in range(count):
        worker_id = f"worker-{i}"
        cmd = [
            sys.executable, "-m", "app.worker.pg_worker_main",
            "--worker-id", worker_id,
            "--fast-interval", str(fast_interval),
            "--slow-interval", str(slow_interval),
        ]
        
        proc = subprocess.Popen(cmd)
        procs.append(proc)
        print(f"Started {worker_id} (PID: {proc.pid})")
        time.sleep(0.5)  # 错开启动时间
    
    return procs


def main():
    parser = argparse.ArgumentParser(description="Start multiple EasyRAG workers")
    parser.add_argument("--count", type=int, default=3, help="Number of workers to start")
    parser.add_argument("--fast-interval", type=float, default=0.1, help="Fast poll interval")
    parser.add_argument("--slow-interval", type=float, default=5.0, help="Slow poll interval")
    
    args = parser.parse_args()
    
    procs = start_workers(args.count, args.fast_interval, args.slow_interval)
    
    print(f"\n=== {len(procs)} workers running ===")
    print("Press Ctrl+C to stop all workers\n")
    
    try:
        for proc in procs:
            proc.wait()
    except KeyboardInterrupt:
        print("\nStopping workers...")
        for proc in procs:
            proc.terminate()
            proc.wait()
        print("All workers stopped")


if __name__ == "__main__":
    main()
