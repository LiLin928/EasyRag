"""PostgreSQL Worker 启动入口。

用法: python -m app.worker.pg_worker_main [--worker-id ID] [--fast-interval SEC] [--slow-interval SEC]
"""
import argparse
import asyncio
import signal
import sys
from typing import Optional

from app.worker.pg_worker import PGWorker


# Global worker instance for signal handling
_worker: Optional[PGWorker] = None


def _signal_handler(signum, frame):
    """Handle SIGINT/SIGTERM for graceful shutdown."""
    print(f"\nReceived signal {signum}, initiating graceful shutdown...")
    global _worker
    if _worker is not None:
        _worker._shutdown = True


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PostgreSQL Worker for EasyRAG workflow execution"
    )
    parser.add_argument(
        "--worker-id",
        type=str,
        default=None,
        help="Unique worker identifier (auto-generated if not provided)"
    )
    parser.add_argument(
        "--fast-interval",
        type=float,
        default=0.1,
        help="Fast poll interval in seconds when jobs are available (default: 0.1)"
    )
    parser.add_argument(
        "--slow-interval",
        type=float,
        default=5.0,
        help="Slow poll interval in seconds when queue is empty (default: 5.0)"
    )
    
    args = parser.parse_args()
    
    # Register signal handlers
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)
    
    # Create worker
    global _worker
    _worker = PGWorker(
        poll_interval_fast=args.fast_interval,
        poll_interval_slow=args.slow_interval,
        worker_id=args.worker_id
    )
    
    print(f"Starting PostgreSQL Worker: {_worker.worker_id}")
    print(f"  Fast poll interval: {_worker.poll_interval_fast}s")
    print(f"  Slow poll interval: {_worker.poll_interval_slow}s")
    print("Press Ctrl+C to stop gracefully\n")
    
    try:
        await _worker.run()
    except Exception as e:
        print(f"Worker error: {e}")
        sys.exit(1)
    
    print("Worker stopped gracefully")


if __name__ == "__main__":
    asyncio.run(main())
