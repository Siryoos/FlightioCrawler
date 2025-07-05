import asyncio
from monitoring.production_memory_monitor import ProductionMemoryMonitor

if __name__ == "__main__":
    monitor = ProductionMemoryMonitor()
    try:
        asyncio.run(monitor.start_monitoring())
    except KeyboardInterrupt:
        print("\nProduction monitoring stopped by user.")
        asyncio.run(monitor.stop_monitoring()) 