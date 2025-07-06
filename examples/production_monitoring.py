"""Run production monitoring using the unified monitoring package."""

import asyncio
from monitoring import UnifiedMonitor


def main() -> None:
    monitor = UnifiedMonitor()
    try:
        asyncio.run(monitor.start())
    except KeyboardInterrupt:
        print("\nProduction monitoring stopped by user.")
        asyncio.run(monitor.stop())


if __name__ == "__main__":
    main()
