import asyncio
import platform
from monitor import ContentMonitor

async def main(max_concurrent=5, max_retries=2, timeout=10000):
    """Main function for single run"""
    monitor = ContentMonitor(max_concurrent=max_concurrent, max_retries=max_retries, timeout=timeout)

    # Load URLs
    monitor.load_urls_from_csv()

    # Check all URLs once
    await monitor.check_all_urls()

if __name__ == "__main__":
    # Set proper event loop policy for Windows subprocess support (needed for Playwright)
    if platform.system() == 'Windows':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    import argparse

    parser = argparse.ArgumentParser(description='Content monitoring tool')
    parser.add_argument('--monitor', action='store_true', help='Run continuous monitoring')
    parser.add_argument('--max-concurrent', type=int, default=5,
                       help='Maximum number of concurrent URL extractions (default: 5)')
    parser.add_argument('--max-retries', type=int, default=2,
                       help='Maximum number of retries for failed requests (default: 2)')
    parser.add_argument('--timeout', type=int, default=10000,
                       help='Timeout in milliseconds for page loading (default: 10000)')
    parser.add_argument('--interval', type=int, default=1,
                       help='Monitoring interval in minutes (default: 1)')
    parser.add_argument('--check-interval', type=float, default=1.0,
                       help='Check interval in seconds for monitoring loop (default: 1.0)')

    args = parser.parse_args()

    if args.monitor:
        # Run continuous monitoring
        monitor = ContentMonitor(
            max_concurrent=args.max_concurrent,
            max_retries=args.max_retries,
            timeout=args.timeout,
            monitoring_interval=args.interval,
            check_interval=args.check_interval
        )
        monitor.run_monitoring_loop()
    else:
        # Run single check
        asyncio.run(main(args.max_concurrent, args.max_retries, args.timeout))
