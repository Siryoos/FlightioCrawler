"""
Performance Profiler for Flight Crawler System
Comprehensive memory monitoring, profiling tools, and benchmarking
"""

import asyncio
import gc
import cProfile
import pstats
import io
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Union
from dataclasses import dataclass, asdict
from pathlib import Path
import psutil
import os
import weakref
from functools import wraps, lru_cache
from contextlib import contextmanager, asynccontextmanager
import statistics

try:
    from memory_profiler import profile as memory_profile
    from line_profiler import LineProfiler
    PROFILER_AVAILABLE = True
except ImportError:
    PROFILER_AVAILABLE = False
    memory_profile = lambda func: func  # Dummy decorator
    LineProfiler = None


@dataclass
class MemorySnapshot:
    """Memory usage snapshot"""
    timestamp: datetime
    rss_mb: float  # Resident Set Size
    vms_mb: float  # Virtual Memory Size
    percent: float  # Memory percentage
    available_mb: float
    peak_rss_mb: float = 0.0
    gc_count: Dict[str, int] = None
    
    def __post_init__(self):
        if self.gc_count is None:
            self.gc_count = {f"gen_{i}": gc.get_count()[i] for i in range(3)}


@dataclass
class PerformanceMetrics:
    """Performance metrics for a crawler operation"""
    operation_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    memory_before: MemorySnapshot
    memory_after: MemorySnapshot
    memory_peak: MemorySnapshot
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None
    custom_metrics: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.custom_metrics is None:
            self.custom_metrics = {}


@dataclass
class CrawlerProfile:
    """Complete profile for a crawler"""
    crawler_name: str
    total_operations: int
    successful_operations: int
    failed_operations: int
    avg_duration: float
    avg_memory_usage: float
    peak_memory_usage: float
    memory_efficiency_score: float
    performance_score: float
    bottlenecks: List[str]
    recommendations: List[str]


class PerformanceProfiler:
    """
    Comprehensive performance profiler for crawler system
    """
    
    def __init__(self, output_dir: str = "performance_reports"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logger()
        self.metrics_history: List[PerformanceMetrics] = []
        self.baseline_metrics: Dict[str, Any] = {}
        self.memory_snapshots: List[MemorySnapshot] = []
        
        # Memory monitoring settings
        self.memory_threshold_mb = 1024  # 1GB threshold
        self.enable_detailed_profiling = True
        self.profile_line_by_line = False
        
        # CPU profiler
        self.cpu_profiler = cProfile.Profile()
        self.line_profiler = LineProfiler() if PROFILER_AVAILABLE and LineProfiler else None
        
        # Process tracking
        self.process = psutil.Process(os.getpid())
        self.baseline_memory = self._get_memory_snapshot()
        
        # Leak detection
        self.object_tracker = weakref.WeakSet()
        self.memory_leak_threshold = 100  # MB increase over baseline

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for profiler"""
        logger = logging.getLogger("PerformanceProfiler")
        if not logger.handlers:
            handler = logging.FileHandler(self.output_dir / "profiler.log")
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _get_memory_snapshot(self) -> MemorySnapshot:
        """Get current memory snapshot"""
        try:
            memory_info = self.process.memory_info()
            memory_percent = self.process.memory_percent()
            virtual_memory = psutil.virtual_memory()
            
            return MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=memory_info.rss / 1024 / 1024,
                vms_mb=memory_info.vms / 1024 / 1024,
                percent=memory_percent,
                available_mb=virtual_memory.available / 1024 / 1024,
                gc_count={f"gen_{i}": gc.get_count()[i] for i in range(3)}
            )
        except Exception as e:
            self.logger.error(f"Error getting memory snapshot: {e}")
            return MemorySnapshot(
                timestamp=datetime.now(),
                rss_mb=0, vms_mb=0, percent=0, available_mb=0
            )

    @asynccontextmanager
    async def profile_async_operation(self, operation_name: str):
        """Context manager for profiling async operations"""
        start_time = datetime.now()
        memory_before = self._get_memory_snapshot()
        cpu_before = self.process.cpu_percent()
        
        success = True
        error_message = None
        peak_memory = memory_before
        
        try:
            # Start CPU profiling if enabled
            if self.enable_detailed_profiling:
                self.cpu_profiler.enable()
            
            yield
            
        except Exception as e:
            success = False
            error_message = str(e)
            self.logger.error(f"Operation {operation_name} failed: {e}")
            raise
        finally:
            # Stop CPU profiling
            if self.enable_detailed_profiling:
                self.cpu_profiler.disable()
            
            end_time = datetime.now()
            memory_after = self._get_memory_snapshot()
            cpu_after = self.process.cpu_percent()
            
            # Calculate peak memory during operation
            peak_memory = max([memory_before, memory_after], key=lambda x: x.rss_mb)
            
            # Create performance metrics
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                memory_before=memory_before,
                memory_after=memory_after,
                memory_peak=peak_memory,
                cpu_percent=(cpu_after + cpu_before) / 2,
                success=success,
                error_message=error_message
            )
            
            self.metrics_history.append(metrics)
            self._check_memory_leaks(memory_before, memory_after)
            
            # Log performance summary
            self.logger.info(
                f"Operation '{operation_name}': "
                f"Duration={metrics.duration_seconds:.2f}s, "
                f"Memory={memory_after.rss_mb:.1f}MB "
                f"(Δ{(memory_after.rss_mb - memory_before.rss_mb):+.1f}MB), "
                f"Success={success}"
            )

    @contextmanager
    def profile_sync_operation(self, operation_name: str):
        """Context manager for profiling sync operations"""
        start_time = datetime.now()
        memory_before = self._get_memory_snapshot()
        cpu_before = self.process.cpu_percent()
        
        success = True
        error_message = None
        
        try:
            if self.enable_detailed_profiling:
                self.cpu_profiler.enable()
            
            yield
            
        except Exception as e:
            success = False
            error_message = str(e)
            self.logger.error(f"Operation {operation_name} failed: {e}")
            raise
        finally:
            if self.enable_detailed_profiling:
                self.cpu_profiler.disable()
            
            end_time = datetime.now()
            memory_after = self._get_memory_snapshot()
            cpu_after = self.process.cpu_percent()
            
            peak_memory = max([memory_before, memory_after], key=lambda x: x.rss_mb)
            
            metrics = PerformanceMetrics(
                operation_name=operation_name,
                start_time=start_time,
                end_time=end_time,
                duration_seconds=(end_time - start_time).total_seconds(),
                memory_before=memory_before,
                memory_after=memory_after,
                memory_peak=peak_memory,
                cpu_percent=(cpu_after + cpu_before) / 2,
                success=success,
                error_message=error_message
            )
            
            self.metrics_history.append(metrics)
            self._check_memory_leaks(memory_before, memory_after)

    def profile_function(self, func: Callable) -> Callable:
        """Decorator for profiling functions"""
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            async with self.profile_async_operation(func.__name__):
                return await func(*args, **kwargs)
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            with self.profile_sync_operation(func.__name__):
                return func(*args, **kwargs)
        
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    def _check_memory_leaks(self, before: MemorySnapshot, after: MemorySnapshot):
        """Check for potential memory leaks"""
        memory_increase = after.rss_mb - before.rss_mb
        
        if memory_increase > self.memory_leak_threshold:
            self.logger.warning(
                f"Potential memory leak detected: "
                f"{memory_increase:.1f}MB increase "
                f"(before: {before.rss_mb:.1f}MB, after: {after.rss_mb:.1f}MB)"
            )
            
            # Force garbage collection
            collected = gc.collect()
            gc_after = self._get_memory_snapshot()
            
            self.logger.info(
                f"Garbage collection: collected {collected} objects, "
                f"memory after GC: {gc_after.rss_mb:.1f}MB "
                f"(freed {after.rss_mb - gc_after.rss_mb:.1f}MB)"
            )

    def start_continuous_monitoring(self, interval_seconds: int = 60):
        """Start continuous memory monitoring"""
        def monitor():
            while True:
                snapshot = self._get_memory_snapshot()
                self.memory_snapshots.append(snapshot)
                
                if snapshot.rss_mb > self.memory_threshold_mb:
                    self.logger.warning(
                        f"Memory usage ({snapshot.rss_mb:.1f}MB) exceeds threshold "
                        f"({self.memory_threshold_mb}MB)"
                    )
                
                time.sleep(interval_seconds)
        
        import threading
        monitor_thread = threading.Thread(target=monitor, daemon=True)
        monitor_thread.start()
        self.logger.info("Started continuous memory monitoring")

    def generate_performance_report(self) -> Dict[str, Any]:
        """Generate comprehensive performance report"""
        if not self.metrics_history:
            return {"error": "No performance metrics available"}
        
        # Calculate statistics
        successful_operations = [m for m in self.metrics_history if m.success]
        failed_operations = [m for m in self.metrics_history if not m.success]
        
        durations = [m.duration_seconds for m in successful_operations]
        memory_usage = [m.memory_after.rss_mb for m in self.metrics_history]
        memory_deltas = [
            m.memory_after.rss_mb - m.memory_before.rss_mb 
            for m in self.metrics_history
        ]
        
        report = {
            "summary": {
                "total_operations": len(self.metrics_history),
                "successful_operations": len(successful_operations),
                "failed_operations": len(failed_operations),
                "success_rate": len(successful_operations) / len(self.metrics_history) * 100,
                "total_duration": sum(durations),
                "report_generated_at": datetime.now().isoformat()
            },
            "performance_metrics": {
                "avg_duration_seconds": statistics.mean(durations) if durations else 0,
                "median_duration_seconds": statistics.median(durations) if durations else 0,
                "min_duration_seconds": min(durations) if durations else 0,
                "max_duration_seconds": max(durations) if durations else 0,
                "std_duration_seconds": statistics.stdev(durations) if len(durations) > 1 else 0
            },
            "memory_metrics": {
                "avg_memory_usage_mb": statistics.mean(memory_usage) if memory_usage else 0,
                "peak_memory_usage_mb": max(memory_usage) if memory_usage else 0,
                "avg_memory_delta_mb": statistics.mean(memory_deltas) if memory_deltas else 0,
                "memory_leak_indicators": len([d for d in memory_deltas if d > 50]),  # >50MB increases
                "baseline_memory_mb": self.baseline_memory.rss_mb
            },
            "bottlenecks": self._identify_bottlenecks(),
            "recommendations": self._generate_recommendations()
        }
        
        return report

    def _identify_bottlenecks(self) -> List[str]:
        """Identify performance bottlenecks"""
        bottlenecks = []
        
        if not self.metrics_history:
            return bottlenecks
        
        durations = [m.duration_seconds for m in self.metrics_history if m.success]
        memory_deltas = [
            m.memory_after.rss_mb - m.memory_before.rss_mb 
            for m in self.metrics_history
        ]
        
        if durations:
            avg_duration = statistics.mean(durations)
            slow_operations = [
                m for m in self.metrics_history 
                if m.success and m.duration_seconds > avg_duration * 2
            ]
            
            if slow_operations:
                bottlenecks.append(
                    f"Slow operations detected: {len(slow_operations)} operations "
                    f"took >2x average time ({avg_duration:.2f}s)"
                )
        
        if memory_deltas:
            high_memory_ops = [d for d in memory_deltas if d > 100]  # >100MB
            if high_memory_ops:
                bottlenecks.append(
                    f"High memory usage: {len(high_memory_ops)} operations "
                    f"used >100MB memory"
                )
        
        return bottlenecks

    def _generate_recommendations(self) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        if not self.metrics_history:
            return recommendations
        
        # Memory recommendations
        memory_deltas = [
            m.memory_after.rss_mb - m.memory_before.rss_mb 
            for m in self.metrics_history
        ]
        
        if memory_deltas and statistics.mean(memory_deltas) > 20:
            recommendations.append(
                "Consider implementing more aggressive garbage collection - "
                "average memory increase per operation is high"
            )
        
        # Duration recommendations
        durations = [m.duration_seconds for m in self.metrics_history if m.success]
        if durations and statistics.mean(durations) > 30:
            recommendations.append(
                "Operations are taking >30s on average - "
                "consider optimizing selectors and wait strategies"
            )
        
        # Error rate recommendations
        error_rate = len([m for m in self.metrics_history if not m.success]) / len(self.metrics_history)
        if error_rate > 0.1:  # >10% error rate
            recommendations.append(
                f"High error rate ({error_rate*100:.1f}%) - "
                "review error handling and retry mechanisms"
            )
        
        return recommendations

    def save_report(self, filename: Optional[str] = None) -> str:
        """Save performance report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"performance_report_{timestamp}.json"
        
        report = self.generate_performance_report()
        report_path = self.output_dir / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"Performance report saved to {report_path}")
        return str(report_path)

    def save_cpu_profile(self, filename: Optional[str] = None) -> str:
        """Save CPU profile statistics"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"cpu_profile_{timestamp}.txt"
        
        profile_path = self.output_dir / filename
        
        s = io.StringIO()
        ps = pstats.Stats(self.cpu_profiler, stream=s)
        ps.sort_stats('cumulative')
        ps.print_stats(50)  # Top 50 functions
        
        with open(profile_path, 'w') as f:
            f.write(s.getvalue())
        
        self.logger.info(f"CPU profile saved to {profile_path}")
        return str(profile_path)

    def compare_with_baseline(self, baseline_report_path: str) -> Dict[str, Any]:
        """Compare current performance with baseline"""
        try:
            with open(baseline_report_path, 'r') as f:
                baseline = json.load(f)
            
            current = self.generate_performance_report()
            
            comparison = {
                "baseline_file": baseline_report_path,
                "comparison_date": datetime.now().isoformat(),
                "improvements": {},
                "regressions": {},
                "overall_change": {}
            }
            
            # Compare key metrics
            metrics_to_compare = [
                ("avg_duration_seconds", "performance_metrics"),
                ("avg_memory_usage_mb", "memory_metrics"),
                ("peak_memory_usage_mb", "memory_metrics"),
                ("success_rate", "summary")
            ]
            
            for metric, section in metrics_to_compare:
                current_val = current.get(section, {}).get(metric, 0)
                baseline_val = baseline.get(section, {}).get(metric, 0)
                
                if baseline_val > 0:
                    change_percent = ((current_val - baseline_val) / baseline_val) * 100
                    comparison["overall_change"][metric] = {
                        "current": current_val,
                        "baseline": baseline_val,
                        "change_percent": change_percent
                    }
                    
                    if change_percent < -5:  # >5% improvement
                        comparison["improvements"][metric] = abs(change_percent)
                    elif change_percent > 5:  # >5% regression
                        comparison["regressions"][metric] = change_percent
            
            return comparison
            
        except Exception as e:
            self.logger.error(f"Error comparing with baseline: {e}")
            return {"error": str(e)}

    def reset_metrics(self):
        """Reset all metrics and start fresh"""
        self.metrics_history.clear()
        self.memory_snapshots.clear()
        self.cpu_profiler = cProfile.Profile()
        if self.line_profiler:
            self.line_profiler = LineProfiler()
        
        # Force garbage collection
        gc.collect()
        self.baseline_memory = self._get_memory_snapshot()
        
        self.logger.info("Performance metrics reset")


# Global profiler instance
_global_profiler = None

def get_profiler() -> PerformanceProfiler:
    """Get global profiler instance"""
    global _global_profiler
    if _global_profiler is None:
        _global_profiler = PerformanceProfiler()
    return _global_profiler

def profile_crawler_operation(operation_name: str):
    """Decorator for profiling crawler operations"""
    def decorator(func):
        profiler = get_profiler()
        return profiler.profile_function(func)
    return decorator


if __name__ == "__main__":
    # Example usage
    profiler = PerformanceProfiler()
    
    @profile_crawler_operation("test_operation")
    async def test_async_operation():
        await asyncio.sleep(1)
        # Simulate some memory usage
        data = [i for i in range(100000)]
        return len(data)
    
    async def main():
        profiler.start_continuous_monitoring(interval_seconds=5)
        
        # Run test operations
        for i in range(5):
            await test_async_operation()
            await asyncio.sleep(2)
        
        # Generate and save report
        report = profiler.generate_performance_report()
        report_path = profiler.save_report()
        cpu_profile_path = profiler.save_cpu_profile()
        
        print(f"Performance report saved to: {report_path}")
        print(f"CPU profile saved to: {cpu_profile_path}")
        print(f"Success rate: {report['summary']['success_rate']:.1f}%")
        print(f"Average duration: {report['performance_metrics']['avg_duration_seconds']:.2f}s")
        print(f"Peak memory: {report['memory_metrics']['peak_memory_usage_mb']:.1f}MB")
    
    asyncio.run(main()) 