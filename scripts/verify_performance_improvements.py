"""
Performance Improvement Verification Script
Measures and verifies 40%+ performance improvement from optimizations
"""

import asyncio
import time
import json
import statistics
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
from pathlib import Path
import gc
import psutil
import os

# Import our components
try:
    from scripts.memory_benchmark_suite import MemoryBenchmarkRunner, create_default_benchmark_tests
    from scripts.performance_profiler import get_profiler
    from scripts.memory_leak_detector import get_leak_detector
    from utils.memory_efficient_cache import get_cache
    from utils.lazy_loader import get_airport_loader, get_config_loader
    from adapters.site_adapters.iranian_airlines.alibaba_adapter import AlibabaAdapter
    from monitoring.health_checks import get_health_checker
    COMPONENTS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import some components: {e}")
    COMPONENTS_AVAILABLE = False


@dataclass
class PerformanceComparison:
    """Comparison between baseline and optimized performance"""
    metric_name: str
    baseline_value: float
    optimized_value: float
    improvement_percent: float
    target_improvement: float
    meets_target: bool
    unit: str
    description: str


@dataclass
class VerificationReport:
    """Complete verification report"""
    timestamp: datetime
    overall_improvement_percent: float
    target_improvement_percent: float
    overall_meets_target: bool
    baseline_path: Optional[str]
    optimized_path: str
    comparisons: List[PerformanceComparison]
    test_results: Dict[str, Any]
    recommendations: List[str]
    summary: str


class PerformanceVerifier:
    """
    Comprehensive performance verification system
    """
    
    def __init__(
        self, 
        baseline_path: Optional[str] = None,
        target_improvement_percent: float = 40.0,
        output_dir: str = "verification_results"
    ):
        self.baseline_path = baseline_path
        self.target_improvement_percent = target_improvement_percent
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
        
        self.logger = self._setup_logger()
        self.benchmark_runner = MemoryBenchmarkRunner(str(self.output_dir / "benchmarks"))
        
        # Create benchmark tests
        create_default_benchmark_tests(self.benchmark_runner)
        
        # Add performance-specific tests
        self._add_performance_tests()

    def _setup_logger(self) -> logging.Logger:
        """Setup logger"""
        logger = logging.getLogger("PerformanceVerifier")
        if not logger.handlers:
            handler = logging.FileHandler(self.output_dir / "verification.log")
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def _add_performance_tests(self):
        """Add performance-specific tests"""
        
        @self.benchmark_runner.register_test("crawler_full_cycle")
        async def test_crawler_full_cycle():
            """Test complete crawler cycle with real adapter"""
            if not COMPONENTS_AVAILABLE:
                return
            
            # Test with optimized Alibaba adapter
            async with AlibabaAdapter() as adapter:
                search_params = {
                    "origin": "THR",
                    "destination": "IST", 
                    "departure_date": "2024-06-15",
                    "passengers": 1
                }
                
                # Simulate search (without actual network calls in test)
                await adapter._setup_browser()
                
                # Test memory efficiency
                resource_usage = adapter.get_resource_usage()
                assert resource_usage["memory_usage_mb"] < 200  # Should be under 200MB
        
        @self.benchmark_runner.register_test("concurrent_cache_operations")
        async def test_concurrent_cache_operations():
            """Test concurrent cache operations"""
            cache = get_cache("performance_test", max_size_mb=50)
            
            # Concurrent write operations
            async def write_data(start_idx: int, count: int):
                for i in range(start_idx, start_idx + count):
                    cache.set(f"key_{i}", f"value_{i}" * 100)
            
            # Run concurrent writes
            tasks = [
                write_data(0, 250),
                write_data(250, 250),
                write_data(500, 250),
                write_data(750, 250)
            ]
            await asyncio.gather(*tasks)
            
            # Concurrent read operations
            async def read_data(start_idx: int, count: int):
                for i in range(start_idx, start_idx + count):
                    _ = cache.get(f"key_{i}")
            
            # Run concurrent reads
            tasks = [
                read_data(0, 250),
                read_data(250, 250),
                read_data(500, 250),
                read_data(750, 250)
            ]
            await asyncio.gather(*tasks)
            
            # Cleanup
            cache.clear()
        
        @self.benchmark_runner.register_test("lazy_loading_efficiency")
        async def test_lazy_loading_efficiency():
            """Test lazy loading efficiency"""
            airport_loader = get_airport_loader()
            config_loader = get_config_loader()
            
            # Test airport loading
            airport = airport_loader.get_airport_by_code("THR")
            assert airport is not None
            
            # Test search functionality
            results = airport_loader.search_airports("tehran", limit=5)
            assert len(results) > 0
            
            # Test config loading
            config = config_loader.load_site_config("alibaba")
            assert config is not None
            
            # Test memory efficiency of generators
            count = 0
            for airport in airport_loader.get_airports_by_country("IR"):
                count += 1
                if count >= 100:  # Limit for test
                    break
            
            assert count > 0
        
        @self.benchmark_runner.register_test("memory_optimization_validation")
        async def test_memory_optimization():
            """Test memory optimization features"""
            initial_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Create some objects to test cleanup
            large_objects = []
            for i in range(100):
                # Create objects that should be garbage collected
                obj = [j for j in range(1000)]
                large_objects.append(obj)
            
            mid_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Clear and force cleanup
            large_objects.clear()
            gc.collect()
            
            final_memory = psutil.Process().memory_info().rss / 1024 / 1024
            
            # Memory should have decreased after cleanup
            memory_freed = mid_memory - final_memory
            assert memory_freed > 0, f"Memory not freed efficiently: {memory_freed}MB"
            
            self.logger.info(f"Memory optimization test: freed {memory_freed:.1f}MB")

    async def run_baseline_benchmark(self, save_baseline: bool = True) -> str:
        """Run baseline benchmark and optionally save it"""
        self.logger.info("Running baseline benchmark...")
        
        baseline_suite = await self.benchmark_runner.run_benchmark_suite(
            "baseline_performance",
            iterations=3
        )
        
        baseline_path = self.benchmark_runner.save_results(baseline_suite, "baseline_benchmark.json")
        
        if save_baseline:
            self.baseline_path = baseline_path
        
        self.logger.info(f"Baseline benchmark completed: {baseline_path}")
        return baseline_path

    async def run_optimized_benchmark(self) -> str:
        """Run optimized benchmark"""
        self.logger.info("Running optimized benchmark...")
        
        # Reset benchmark runner to clear any state
        self.benchmark_runner.reset_metrics()
        
        optimized_suite = await self.benchmark_runner.run_benchmark_suite(
            "optimized_performance", 
            iterations=3
        )
        
        optimized_path = self.benchmark_runner.save_results(optimized_suite, "optimized_benchmark.json")
        
        self.logger.info(f"Optimized benchmark completed: {optimized_path}")
        return optimized_path

    def compare_performance(
        self, 
        baseline_path: str, 
        optimized_path: str
    ) -> VerificationReport:
        """Compare baseline and optimized performance"""
        self.logger.info("Comparing performance metrics...")
        
        # Load results
        with open(baseline_path, 'r') as f:
            baseline_data = json.load(f)
        
        with open(optimized_path, 'r') as f:
            optimized_data = json.load(f)
        
        # Compare key metrics
        comparisons = []
        
        # Memory efficiency comparison
        baseline_memory = baseline_data.get("memory_metrics", {}).get("avg_memory_usage_mb", 0)
        optimized_memory = optimized_data.get("memory_metrics", {}).get("avg_memory_usage_mb", 0)
        
        if baseline_memory > 0:
            memory_improvement = ((baseline_memory - optimized_memory) / baseline_memory) * 100
            comparisons.append(PerformanceComparison(
                metric_name="memory_usage",
                baseline_value=baseline_memory,
                optimized_value=optimized_memory,
                improvement_percent=memory_improvement,
                target_improvement=20.0,  # 20% memory improvement target
                meets_target=memory_improvement >= 20.0,
                unit="MB",
                description="Average memory usage reduction"
            ))
        
        # Duration performance comparison
        baseline_duration = baseline_data.get("performance_metrics", {}).get("avg_duration_seconds", 0)
        optimized_duration = optimized_data.get("performance_metrics", {}).get("avg_duration_seconds", 0)
        
        if baseline_duration > 0:
            duration_improvement = ((baseline_duration - optimized_duration) / baseline_duration) * 100
            comparisons.append(PerformanceComparison(
                metric_name="execution_time",
                baseline_value=baseline_duration,
                optimized_value=optimized_duration,
                improvement_percent=duration_improvement,
                target_improvement=30.0,  # 30% speed improvement target
                meets_target=duration_improvement >= 30.0,
                unit="seconds",
                description="Average execution time reduction"
            ))
        
        # Success rate comparison
        baseline_success = baseline_data.get("summary", {}).get("success_rate", 0)
        optimized_success = optimized_data.get("summary", {}).get("success_rate", 0)
        
        success_improvement = optimized_success - baseline_success
        comparisons.append(PerformanceComparison(
            metric_name="success_rate",
            baseline_value=baseline_success,
            optimized_value=optimized_success,
            improvement_percent=success_improvement,
            target_improvement=0.0,  # Should maintain or improve
            meets_target=success_improvement >= 0,
            unit="%",
            description="Success rate change"
        ))
        
        # Peak memory comparison
        baseline_peak = baseline_data.get("memory_metrics", {}).get("peak_memory_usage_mb", 0)
        optimized_peak = optimized_data.get("memory_metrics", {}).get("peak_memory_usage_mb", 0)
        
        if baseline_peak > 0:
            peak_improvement = ((baseline_peak - optimized_peak) / baseline_peak) * 100
            comparisons.append(PerformanceComparison(
                metric_name="peak_memory",
                baseline_value=baseline_peak,
                optimized_value=optimized_peak,
                improvement_percent=peak_improvement,
                target_improvement=25.0,  # 25% peak memory improvement
                meets_target=peak_improvement >= 25.0,
                unit="MB",
                description="Peak memory usage reduction"
            ))
        
        # Calculate overall improvement
        improvement_scores = [
            comp.improvement_percent for comp in comparisons 
            if comp.metric_name in ["memory_usage", "execution_time", "peak_memory"]
        ]
        
        overall_improvement = statistics.mean(improvement_scores) if improvement_scores else 0
        overall_meets_target = overall_improvement >= self.target_improvement_percent
        
        # Generate recommendations
        recommendations = self._generate_recommendations(comparisons, overall_improvement)
        
        # Create summary
        summary = self._create_summary(comparisons, overall_improvement, overall_meets_target)
        
        return VerificationReport(
            timestamp=datetime.now(),
            overall_improvement_percent=overall_improvement,
            target_improvement_percent=self.target_improvement_percent,
            overall_meets_target=overall_meets_target,
            baseline_path=baseline_path,
            optimized_path=optimized_path,
            comparisons=comparisons,
            test_results={
                "baseline": baseline_data,
                "optimized": optimized_data
            },
            recommendations=recommendations,
            summary=summary
        )

    def _generate_recommendations(
        self, 
        comparisons: List[PerformanceComparison],
        overall_improvement: float
    ) -> List[str]:
        """Generate optimization recommendations"""
        recommendations = []
        
        # Check individual metrics
        for comp in comparisons:
            if not comp.meets_target:
                if comp.metric_name == "memory_usage":
                    recommendations.append(
                        "Memory usage improvement below target - consider more aggressive caching strategies"
                    )
                elif comp.metric_name == "execution_time":
                    recommendations.append(
                        "Execution time improvement below target - optimize DOM queries and waiting strategies"
                    )
                elif comp.metric_name == "peak_memory":
                    recommendations.append(
                        "Peak memory improvement below target - implement more frequent garbage collection"
                    )
        
        # Overall recommendations
        if overall_improvement < self.target_improvement_percent:
            gap = self.target_improvement_percent - overall_improvement
            recommendations.append(
                f"Overall improvement ({overall_improvement:.1f}%) is {gap:.1f}% below target "
                f"({self.target_improvement_percent}%) - consider additional optimizations"
            )
        else:
            recommendations.append(
                f"Excellent! Overall improvement ({overall_improvement:.1f}%) exceeds target "
                f"({self.target_improvement_percent}%)"
            )
        
        # Specific optimization suggestions
        if overall_improvement < 20:
            recommendations.extend([
                "Consider implementing connection pooling",
                "Add more aggressive WebDriver optimization flags",
                "Implement object pooling for frequently created objects",
                "Add batch processing for multiple requests"
            ])
        elif overall_improvement < 40:
            recommendations.extend([
                "Fine-tune cache TTL settings",
                "Optimize selector specificity",
                "Review async operation patterns",
                "Consider implementing streaming for large datasets"
            ])
        
        return recommendations

    def _create_summary(
        self,
        comparisons: List[PerformanceComparison],
        overall_improvement: float,
        meets_target: bool
    ) -> str:
        """Create performance summary"""
        summary_parts = []
        
        if meets_target:
            summary_parts.append(
                f"✅ TARGET ACHIEVED: {overall_improvement:.1f}% overall improvement "
                f"(target: {self.target_improvement_percent}%)"
            )
        else:
            summary_parts.append(
                f"❌ TARGET MISSED: {overall_improvement:.1f}% overall improvement "
                f"(target: {self.target_improvement_percent}%)"
            )
        
        # Individual metric summaries
        for comp in comparisons:
            status = "✅" if comp.meets_target else "❌"
            summary_parts.append(
                f"{status} {comp.description}: {comp.improvement_percent:+.1f}% "
                f"({comp.baseline_value:.2f} → {comp.optimized_value:.2f} {comp.unit})"
            )
        
        return "\n".join(summary_parts)

    async def run_full_verification(self) -> VerificationReport:
        """Run complete performance verification"""
        self.logger.info("Starting full performance verification...")
        
        # If no baseline provided, create one
        if not self.baseline_path:
            self.logger.info("No baseline provided, creating baseline benchmark...")
            self.baseline_path = await self.run_baseline_benchmark()
        
        # Run optimized benchmark
        optimized_path = await self.run_optimized_benchmark()
        
        # Compare results
        report = self.compare_performance(self.baseline_path, optimized_path)
        
        # Save verification report
        report_path = self.save_verification_report(report)
        
        self.logger.info(f"Verification completed. Report saved to: {report_path}")
        return report

    def save_verification_report(self, report: VerificationReport) -> str:
        """Save verification report"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"verification_report_{timestamp}.json"
        
        # Convert to dict for JSON serialization
        report_dict = asdict(report)
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, indent=2, ensure_ascii=False, default=str)
        
        # Also save human-readable summary
        summary_path = self.output_dir / f"verification_summary_{timestamp}.txt"
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write("PERFORMANCE VERIFICATION REPORT\n")
            f.write("=" * 50 + "\n\n")
            f.write(f"Timestamp: {report.timestamp}\n")
            f.write(f"Target Improvement: {report.target_improvement_percent}%\n")
            f.write(f"Overall Improvement: {report.overall_improvement_percent:.1f}%\n")
            f.write(f"Target Met: {'YES' if report.overall_meets_target else 'NO'}\n\n")
            
            f.write("SUMMARY\n")
            f.write("-" * 20 + "\n")
            f.write(report.summary + "\n\n")
            
            f.write("DETAILED METRICS\n")
            f.write("-" * 20 + "\n")
            for comp in report.comparisons:
                f.write(f"{comp.metric_name}:\n")
                f.write(f"  Baseline: {comp.baseline_value:.2f} {comp.unit}\n")
                f.write(f"  Optimized: {comp.optimized_value:.2f} {comp.unit}\n")
                f.write(f"  Improvement: {comp.improvement_percent:+.1f}%\n")
                f.write(f"  Target Met: {'YES' if comp.meets_target else 'NO'}\n\n")
            
            f.write("RECOMMENDATIONS\n")
            f.write("-" * 20 + "\n")
            for rec in report.recommendations:
                f.write(f"• {rec}\n")
        
        self.logger.info(f"Human-readable summary saved to: {summary_path}")
        return str(report_path)

    def print_verification_results(self, report: VerificationReport):
        """Print verification results to console"""
        print("\n" + "=" * 60)
        print("PERFORMANCE VERIFICATION RESULTS")
        print("=" * 60)
        
        if report.overall_meets_target:
            print(f"🎉 SUCCESS: {report.overall_improvement_percent:.1f}% improvement achieved!")
            print(f"   Target: {report.target_improvement_percent}%")
        else:
            print(f"❌ TARGET MISSED: {report.overall_improvement_percent:.1f}% improvement")
            print(f"   Target: {report.target_improvement_percent}%")
            gap = report.target_improvement_percent - report.overall_improvement_percent
            print(f"   Gap: {gap:.1f}%")
        
        print("\nDETAILED RESULTS:")
        print("-" * 40)
        
        for comp in report.comparisons:
            status = "✅" if comp.meets_target else "❌"
            print(f"{status} {comp.description}")
            print(f"   {comp.baseline_value:.2f} → {comp.optimized_value:.2f} {comp.unit}")
            print(f"   Improvement: {comp.improvement_percent:+.1f}%")
            print()
        
        if report.recommendations:
            print("RECOMMENDATIONS:")
            print("-" * 40)
            for rec in report.recommendations:
                print(f"• {rec}")
        
        print("=" * 60)


async def main():
    """Main verification execution"""
    verifier = PerformanceVerifier(
        target_improvement_percent=40.0,
        output_dir="verification_results"
    )
    
    try:
        # Run full verification
        report = await verifier.run_full_verification()
        
        # Print results
        verifier.print_verification_results(report)
        
        # Exit with appropriate code
        if report.overall_meets_target:
            print("✅ Performance verification PASSED!")
            return 0
        else:
            print("❌ Performance verification FAILED!")
            return 1
    
    except Exception as e:
        print(f"❌ Verification failed with error: {e}")
        logging.exception("Verification error")
        return 1


if __name__ == "__main__":
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Run verification
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 