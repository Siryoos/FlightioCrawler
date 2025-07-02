"""
Memory Benchmark Suite for Flight Crawler System
Comprehensive performance testing, regression detection, and automated benchmarking
"""

import asyncio
import time
import gc
import psutil
import os
import json
import statistics
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from functools import wraps
import traceback
import subprocess
import sys

# Import our components
try:
    from scripts.performance_profiler import PerformanceProfiler, get_profiler
    from scripts.memory_leak_detector import MemoryLeakDetector, get_leak_detector
    from utils.memory_efficient_cache import get_cache
    from utils.lazy_loader import get_airport_loader, get_config_loader
    from adapters.base_adapters.enhanced_base_crawler import EnhancedBaseCrawler
except ImportError as e:
    print(f"Warning: Could not import some components: {e}")


@dataclass
class BenchmarkResult:
    """Result of a single benchmark test"""
    test_name: str
    start_time: datetime
    end_time: datetime
    duration_seconds: float
    memory_before_mb: float
    memory_after_mb: float
    memory_peak_mb: float
    memory_delta_mb: float
    cpu_percent: float
    success: bool
    error_message: Optional[str] = None
    custom_metrics: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def memory_efficiency_score(self) -> float:
        """Calculate memory efficiency score (0-100)"""
        if self.memory_delta_mb <= 0:
            return 100.0
        
        # Penalty for memory growth, bonus for cleanup
        base_score = max(0, 100 - (self.memory_delta_mb * 2))
        
        # Bonus for short duration with low memory usage
        if self.duration_seconds < 10 and self.memory_peak_mb < 100:
            base_score += 10
        
        return min(100.0, base_score)
    
    @property
    def performance_score(self) -> float:
        """Calculate overall performance score (0-100)"""
        memory_score = self.memory_efficiency_score
        
        # Time-based score (assuming 30s is reasonable target)
        time_score = max(0, 100 - (self.duration_seconds * 2))
        
        # CPU efficiency score
        cpu_score = max(0, 100 - self.cpu_percent)
        
        # Weighted average
        return (memory_score * 0.5 + time_score * 0.3 + cpu_score * 0.2)


@dataclass
class BenchmarkSuite:
    """Collection of benchmark results"""
    suite_name: str
    start_time: datetime
    end_time: datetime
    results: List[BenchmarkResult]
    baseline_path: Optional[str] = None
    environment_info: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def total_duration_seconds(self) -> float:
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        successful = len([r for r in self.results if r.success])
        return (successful / len(self.results)) * 100
    
    @property
    def avg_memory_efficiency(self) -> float:
        if not self.results:
            return 0.0
        scores = [r.memory_efficiency_score for r in self.results if r.success]
        return statistics.mean(scores) if scores else 0.0
    
    @property
    def avg_performance_score(self) -> float:
        if not self.results:
            return 0.0
        scores = [r.performance_score for r in self.results if r.success]
        return statistics.mean(scores) if scores else 0.0


class MemoryBenchmarkRunner:
    """
    Comprehensive benchmark runner for memory and performance testing
    """
    
    def __init__(self, output_dir: str = "benchmark_results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logger()
        self.process = psutil.Process(os.getpid())
        
        # Components
        self.profiler = get_profiler()
        self.leak_detector = get_leak_detector()
        
        # Test registry
        self.benchmark_tests: Dict[str, Callable] = {}
        self.setup_hooks: List[Callable] = []
        self.teardown_hooks: List[Callable] = []
        
        # Results storage
        self.current_suite: Optional[BenchmarkSuite] = None
        self.baseline_suite: Optional[BenchmarkSuite] = None

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for benchmark runner"""
        logger = logging.getLogger("BenchmarkRunner")
        if not logger.handlers:
            handler = logging.FileHandler(self.output_dir / "benchmark.log")
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def register_test(self, name: str):
        """Decorator to register benchmark test"""
        def decorator(func):
            self.benchmark_tests[name] = func
            return func
        return decorator

    def add_setup_hook(self, func: Callable):
        """Add setup hook to run before each test"""
        self.setup_hooks.append(func)

    def add_teardown_hook(self, func: Callable):
        """Add teardown hook to run after each test"""
        self.teardown_hooks.append(func)

    async def run_benchmark_suite(
        self, 
        suite_name: str,
        tests_to_run: Optional[List[str]] = None,
        iterations: int = 1
    ) -> BenchmarkSuite:
        """Run complete benchmark suite"""
        self.logger.info(f"Starting benchmark suite: {suite_name}")
        
        start_time = datetime.now()
        results = []
        
        # Determine which tests to run
        if tests_to_run is None:
            tests_to_run = list(self.benchmark_tests.keys())
        
        # Get environment info
        env_info = self._get_environment_info()
        
        # Run each test
        for test_name in tests_to_run:
            if test_name not in self.benchmark_tests:
                self.logger.warning(f"Test '{test_name}' not found")
                continue
            
            self.logger.info(f"Running test: {test_name}")
            
            # Run test multiple times if requested
            for iteration in range(iterations):
                try:
                    result = await self._run_single_test(test_name, iteration)
                    results.append(result)
                    
                    # Log intermediate result
                    self.logger.info(
                        f"Test {test_name} iteration {iteration + 1}: "
                        f"Duration={result.duration_seconds:.2f}s, "
                        f"Memory Δ={result.memory_delta_mb:+.1f}MB, "
                        f"Score={result.performance_score:.1f}"
                    )
                    
                except Exception as e:
                    self.logger.error(f"Test {test_name} iteration {iteration + 1} failed: {e}")
                    # Create failed result
                    result = BenchmarkResult(
                        test_name=f"{test_name}_iter_{iteration}",
                        start_time=datetime.now(),
                        end_time=datetime.now(),
                        duration_seconds=0,
                        memory_before_mb=0,
                        memory_after_mb=0,
                        memory_peak_mb=0,
                        memory_delta_mb=0,
                        cpu_percent=0,
                        success=False,
                        error_message=str(e)
                    )
                    results.append(result)
        
        end_time = datetime.now()
        
        # Create suite
        suite = BenchmarkSuite(
            suite_name=suite_name,
            start_time=start_time,
            end_time=end_time,
            results=results,
            environment_info=env_info
        )
        
        self.current_suite = suite
        
        self.logger.info(
            f"Benchmark suite completed: {len(results)} tests, "
            f"success rate: {suite.success_rate:.1f}%, "
            f"avg performance score: {suite.avg_performance_score:.1f}"
        )
        
        return suite

    async def _run_single_test(self, test_name: str, iteration: int) -> BenchmarkResult:
        """Run a single benchmark test"""
        test_func = self.benchmark_tests[test_name]
        
        # Run setup hooks
        for hook in self.setup_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception as e:
                self.logger.warning(f"Setup hook failed: {e}")
        
        # Force garbage collection before test
        gc.collect()
        
        # Get initial metrics
        start_time = datetime.now()
        memory_before = self.process.memory_info().rss / 1024 / 1024
        cpu_before = self.process.cpu_percent()
        
        # Track peak memory
        peak_memory = memory_before
        success = True
        error_message = None
        
        try:
            # Monitor memory during test
            async def memory_monitor():
                nonlocal peak_memory
                while True:
                    current_memory = self.process.memory_info().rss / 1024 / 1024
                    peak_memory = max(peak_memory, current_memory)
                    await asyncio.sleep(0.1)
            
            monitor_task = asyncio.create_task(memory_monitor())
            
            # Run the actual test
            try:
                if asyncio.iscoroutinefunction(test_func):
                    await test_func()
                else:
                    test_func()
            finally:
                monitor_task.cancel()
                try:
                    await monitor_task
                except asyncio.CancelledError:
                    pass
        
        except Exception as e:
            success = False
            error_message = str(e)
            self.logger.error(f"Test {test_name} failed: {e}")
        
        # Get final metrics
        end_time = datetime.now()
        memory_after = self.process.memory_info().rss / 1024 / 1024
        cpu_after = self.process.cpu_percent()
        
        # Run teardown hooks
        for hook in self.teardown_hooks:
            try:
                if asyncio.iscoroutinefunction(hook):
                    await hook()
                else:
                    hook()
            except Exception as e:
                self.logger.warning(f"Teardown hook failed: {e}")
        
        return BenchmarkResult(
            test_name=f"{test_name}_iter_{iteration}",
            start_time=start_time,
            end_time=end_time,
            duration_seconds=(end_time - start_time).total_seconds(),
            memory_before_mb=memory_before,
            memory_after_mb=memory_after,
            memory_peak_mb=peak_memory,
            memory_delta_mb=memory_after - memory_before,
            cpu_percent=(cpu_before + cpu_after) / 2,
            success=success,
            error_message=error_message
        )

    def _get_environment_info(self) -> Dict[str, Any]:
        """Get environment information for benchmark context"""
        try:
            return {
                "python_version": sys.version,
                "platform": sys.platform,
                "cpu_count": os.cpu_count(),
                "total_memory_gb": psutil.virtual_memory().total / 1024 / 1024 / 1024,
                "available_memory_gb": psutil.virtual_memory().available / 1024 / 1024 / 1024,
                "timestamp": datetime.now().isoformat(),
                "process_id": os.getpid()
            }
        except Exception as e:
            return {"error": f"Could not get environment info: {e}"}

    def save_results(self, suite: BenchmarkSuite, filename: Optional[str] = None) -> str:
        """Save benchmark results to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"benchmark_{suite.suite_name}_{timestamp}.json"
        
        result_path = self.output_dir / filename
        
        # Convert to dict for JSON serialization
        suite_dict = asdict(suite)
        
        with open(result_path, 'w', encoding='utf-8') as f:
            json.dump(suite_dict, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"Benchmark results saved to {result_path}")
        return str(result_path)

    def load_baseline(self, baseline_path: str) -> BenchmarkSuite:
        """Load baseline benchmark results"""
        try:
            with open(baseline_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Reconstruct BenchmarkSuite from dict
            results = []
            for result_data in data['results']:
                result = BenchmarkResult(**result_data)
                results.append(result)
            
            suite = BenchmarkSuite(
                suite_name=data['suite_name'],
                start_time=datetime.fromisoformat(data['start_time']),
                end_time=datetime.fromisoformat(data['end_time']),
                results=results,
                baseline_path=baseline_path,
                environment_info=data.get('environment_info', {})
            )
            
            self.baseline_suite = suite
            self.logger.info(f"Loaded baseline from {baseline_path}")
            return suite
            
        except Exception as e:
            self.logger.error(f"Error loading baseline: {e}")
            raise

    def compare_with_baseline(self, current_suite: BenchmarkSuite) -> Dict[str, Any]:
        """Compare current results with baseline"""
        if not self.baseline_suite:
            return {"error": "No baseline loaded"}
        
        baseline = self.baseline_suite
        current = current_suite
        
        comparison = {
            "baseline_suite": baseline.suite_name,
            "current_suite": current.suite_name,
            "comparison_date": datetime.now().isoformat(),
            "overall_comparison": {},
            "test_comparisons": {},
            "regression_detected": False,
            "improvements": [],
            "regressions": []
        }
        
        # Overall comparison
        overall_comparison = {
            "success_rate": {
                "baseline": baseline.success_rate,
                "current": current.success_rate,
                "change_percent": ((current.success_rate - baseline.success_rate) / baseline.success_rate * 100) if baseline.success_rate > 0 else 0
            },
            "avg_performance_score": {
                "baseline": baseline.avg_performance_score,
                "current": current.avg_performance_score,
                "change_percent": ((current.avg_performance_score - baseline.avg_performance_score) / baseline.avg_performance_score * 100) if baseline.avg_performance_score > 0 else 0
            },
            "avg_memory_efficiency": {
                "baseline": baseline.avg_memory_efficiency,
                "current": current.avg_memory_efficiency,
                "change_percent": ((current.avg_memory_efficiency - baseline.avg_memory_efficiency) / baseline.avg_memory_efficiency * 100) if baseline.avg_memory_efficiency > 0 else 0
            }
        }
        
        comparison["overall_comparison"] = overall_comparison
        
        # Test-by-test comparison
        baseline_by_test = {}
        for result in baseline.results:
            test_base_name = result.test_name.split('_iter_')[0]
            if test_base_name not in baseline_by_test:
                baseline_by_test[test_base_name] = []
            baseline_by_test[test_base_name].append(result)
        
        current_by_test = {}
        for result in current.results:
            test_base_name = result.test_name.split('_iter_')[0]
            if test_base_name not in current_by_test:
                current_by_test[test_base_name] = []
            current_by_test[test_base_name].append(result)
        
        for test_name in set(baseline_by_test.keys()) | set(current_by_test.keys()):
            baseline_results = baseline_by_test.get(test_name, [])
            current_results = current_by_test.get(test_name, [])
            
            if not baseline_results or not current_results:
                continue
            
            # Calculate averages
            baseline_avg_duration = statistics.mean([r.duration_seconds for r in baseline_results if r.success])
            current_avg_duration = statistics.mean([r.duration_seconds for r in current_results if r.success])
            
            baseline_avg_memory = statistics.mean([r.memory_delta_mb for r in baseline_results if r.success])
            current_avg_memory = statistics.mean([r.memory_delta_mb for r in current_results if r.success])
            
            baseline_avg_score = statistics.mean([r.performance_score for r in baseline_results if r.success])
            current_avg_score = statistics.mean([r.performance_score for r in current_results if r.success])
            
            test_comparison = {
                "duration_change_percent": ((current_avg_duration - baseline_avg_duration) / baseline_avg_duration * 100) if baseline_avg_duration > 0 else 0,
                "memory_change_percent": ((current_avg_memory - baseline_avg_memory) / abs(baseline_avg_memory) * 100) if baseline_avg_memory != 0 else 0,
                "performance_score_change_percent": ((current_avg_score - baseline_avg_score) / baseline_avg_score * 100) if baseline_avg_score > 0 else 0
            }
            
            comparison["test_comparisons"][test_name] = test_comparison
            
            # Detect regressions and improvements
            if test_comparison["performance_score_change_percent"] < -10:  # >10% performance drop
                comparison["regressions"].append(f"{test_name}: {test_comparison['performance_score_change_percent']:.1f}% performance drop")
                comparison["regression_detected"] = True
            elif test_comparison["performance_score_change_percent"] > 10:  # >10% performance improvement
                comparison["improvements"].append(f"{test_name}: {test_comparison['performance_score_change_percent']:.1f}% performance improvement")
        
        return comparison

    def verify_performance_target(self, suite: BenchmarkSuite, target_improvement_percent: float = 40.0) -> Dict[str, Any]:
        """Verify if performance targets are met"""
        if not self.baseline_suite:
            return {"error": "No baseline available for comparison"}
        
        comparison = self.compare_with_baseline(suite)
        
        if "error" in comparison:
            return comparison
        
        overall_improvement = comparison["overall_comparison"]["avg_performance_score"]["change_percent"]
        
        verification = {
            "target_improvement_percent": target_improvement_percent,
            "actual_improvement_percent": overall_improvement,
            "target_met": overall_improvement >= target_improvement_percent,
            "gap_percent": target_improvement_percent - overall_improvement,
            "status": "PASS" if overall_improvement >= target_improvement_percent else "FAIL",
            "recommendations": []
        }
        
        if not verification["target_met"]:
            verification["recommendations"].extend([
                "Review memory optimization strategies",
                "Check for new memory leaks",
                "Optimize slow operations identified in regressions",
                "Consider increasing resource limits if needed"
            ])
        
        return verification


# Pre-defined benchmark tests
def create_default_benchmark_tests(runner: MemoryBenchmarkRunner):
    """Create default benchmark tests"""
    
    @runner.register_test("memory_allocation_cleanup")
    async def test_memory_allocation():
        """Test memory allocation and cleanup"""
        data = []
        for i in range(1000):
            # Allocate memory
            chunk = [j for j in range(1000)]
            data.append(chunk)
        
        # Clear and force cleanup
        data.clear()
        gc.collect()
    
    @runner.register_test("cache_performance")
    async def test_cache_performance():
        """Test cache performance"""
        cache = get_cache("benchmark_test", max_size_mb=10)
        
        # Fill cache
        for i in range(100):
            cache.set(f"key_{i}", f"value_{i}" * 100)
        
        # Access cache
        for i in range(100):
            _ = cache.get(f"key_{i}")
        
        # Clear cache
        cache.clear()
    
    @runner.register_test("airport_data_loading")
    async def test_airport_loading():
        """Test airport data lazy loading"""
        loader = get_airport_loader()
        
        # Load airport data
        airport = loader.get_airport_by_code("THR")
        airports = loader.search_airports("tehran", limit=10)
        popular = loader.get_popular_airports("IR", limit=20)
        
        # Test generator (memory efficient)
        count = 0
        for airport in loader.get_airports_by_country("IR"):
            count += 1
            if count >= 50:  # Limit for test
                break
    
    @runner.register_test("config_loading")
    async def test_config_loading():
        """Test configuration loading"""
        config_loader = get_config_loader()
        
        # Load various configs
        rate_config = config_loader.get_rate_limit_config()
        
        # Test lazy loading of site configs
        count = 0
        for site_name, config in config_loader.load_all_site_configs():
            count += 1
            if count >= 5:  # Limit for test
                break
    
    # Setup and teardown hooks
    def setup_hook():
        """Setup before each test"""
        gc.collect()  # Start with clean memory
    
    def teardown_hook():
        """Cleanup after each test"""
        gc.collect()  # Cleanup after test
    
    runner.add_setup_hook(setup_hook)
    runner.add_teardown_hook(teardown_hook)


async def main():
    """Main benchmark execution"""
    runner = MemoryBenchmarkRunner()
    
    # Create default tests
    create_default_benchmark_tests(runner)
    
    # Run benchmark suite
    suite = await runner.run_benchmark_suite(
        suite_name="memory_optimization_tests",
        iterations=3
    )
    
    # Save results
    results_path = runner.save_results(suite)
    print(f"Benchmark results saved to: {results_path}")
    
    # Print summary
    print(f"\nBenchmark Summary:")
    print(f"Tests run: {len(suite.results)}")
    print(f"Success rate: {suite.success_rate:.1f}%")
    print(f"Average performance score: {suite.avg_performance_score:.1f}")
    print(f"Average memory efficiency: {suite.avg_memory_efficiency:.1f}")
    print(f"Total duration: {suite.total_duration_seconds:.1f}s")
    
    # Test performance verification
    try:
        # Try to load a baseline (you would set this to an actual baseline file)
        # baseline_path = "baseline_benchmark.json"
        # runner.load_baseline(baseline_path)
        # verification = runner.verify_performance_target(suite, 40.0)
        # print(f"Performance target verification: {verification['status']}")
        pass
    except:
        print("No baseline available for comparison")


if __name__ == "__main__":
    asyncio.run(main()) 