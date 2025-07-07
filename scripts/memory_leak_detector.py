"""
Automated Memory Leak Detection System for Flight Crawler
Analyzes memory patterns, tracks object lifetimes, and detects potential leaks
"""

import asyncio
import gc
import sys
import psutil
import os
import threading
import weakref
import tracemalloc
import linecache
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field, asdict
from pathlib import Path
from collections import defaultdict, deque
from functools import wraps
import statistics
import traceback


@dataclass
class MemorySnapshot:
    """Detailed memory snapshot"""
    timestamp: datetime
    rss_mb: float
    vms_mb: float
    peak_rss_mb: float
    available_mb: float
    percent: float
    swap_mb: float
    gc_counts: Dict[int, int]
    object_counts: Dict[str, int]
    top_traces: List[Dict[str, Any]] = field(default_factory=list)
    
    def get_total_objects(self) -> int:
        return sum(self.object_counts.values())


@dataclass
class ObjectLifetime:
    """Track object lifetime and references"""
    object_type: str
    object_id: int
    created_at: datetime
    size_bytes: int
    creation_traceback: List[str]
    reference_count: int
    last_accessed: datetime
    access_count: int = 0
    is_alive: bool = True
    destruction_time: Optional[datetime] = None
    
    def update_access(self):
        self.last_accessed = datetime.now()
        self.access_count += 1
    
    def mark_destroyed(self):
        self.is_alive = False
        self.destruction_time = datetime.now()
    
    @property
    def lifetime_seconds(self) -> float:
        end_time = self.destruction_time or datetime.now()
        return (end_time - self.created_at).total_seconds()


@dataclass
class LeakSuspicion:
    """Information about suspected memory leak"""
    object_type: str
    instance_count: int
    total_size_mb: float
    growth_rate_per_hour: float
    avg_lifetime_hours: float
    oldest_instance_hours: float
    suspicion_score: float
    evidence: List[str]
    recommendations: List[str]
    sample_tracebacks: List[List[str]]


class MemoryLeakDetector:
    """
    Comprehensive memory leak detection system
    """
    
    def __init__(
        self,
        detection_interval_seconds: int = 60,
        snapshot_retention_hours: int = 24,
        leak_threshold_mb: float = 50.0,
        growth_rate_threshold: float = 10.0,  # MB per hour
        enable_tracemalloc: bool = True,
        max_traces: int = 100
    ):
        self.detection_interval = detection_interval_seconds
        self.snapshot_retention = timedelta(hours=snapshot_retention_hours)
        self.leak_threshold_mb = leak_threshold_mb
        self.growth_rate_threshold = growth_rate_threshold
        self.enable_tracemalloc = enable_tracemalloc
        self.max_traces = max_traces
        
        # Data storage
        self.snapshots: deque[MemorySnapshot] = deque()
        self.object_lifetimes: Dict[int, ObjectLifetime] = {}
        self.object_type_stats: Dict[str, List[int]] = defaultdict(list)
        self.leak_suspicions: List[LeakSuspicion] = []
        
        # Monitoring state
        self.is_monitoring = False
        self.monitor_thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        
        # Process info
        self.process = psutil.Process(os.getpid())
        self.baseline_memory: Optional[MemorySnapshot] = None
        
        # Weak reference tracking
        self.tracked_objects: weakref.WeakSet = weakref.WeakSet()
        self.object_callbacks: Dict[int, Callable] = {}
        
        # Logger
        self.logger = self._setup_logger()
        
        # Initialize tracemalloc if enabled
        if self.enable_tracemalloc and not tracemalloc.is_tracing():
            tracemalloc.start(25)  # Keep 25 frames

    def _setup_logger(self) -> logging.Logger:
        """Setup logger for memory leak detector"""
        logger = logging.getLogger("MemoryLeakDetector")
        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)
            logger.setLevel(logging.INFO)
        return logger

    def start_monitoring(self):
        """Start continuous memory monitoring"""
        if self.is_monitoring:
            self.logger.warning("Monitoring already started")
            return
        
        self.is_monitoring = True
        self.stop_event.clear()
        
        # Take baseline snapshot
        self.baseline_memory = self._take_snapshot()
        self.logger.info(f"Baseline memory: {self.baseline_memory.rss_mb:.1f}MB")
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self._monitoring_loop, daemon=True)
        self.monitor_thread.start()
        
        self.logger.info("Memory leak monitoring started")

    def stop_monitoring(self):
        """Stop memory monitoring"""
        if not self.is_monitoring:
            return
        
        self.is_monitoring = False
        self.stop_event.set()
        
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=5)
        
        self.logger.info("Memory leak monitoring stopped")

    def _monitoring_loop(self):
        """Main monitoring loop"""
        while not self.stop_event.wait(self.detection_interval):
            try:
                # Take memory snapshot
                snapshot = self._take_snapshot()
                self.snapshots.append(snapshot)
                
                # Clean old snapshots
                self._cleanup_old_snapshots()
                
                # Analyze for leaks
                self._analyze_memory_patterns()
                
                # Update object lifetime tracking
                self._update_object_tracking()
                
                # Log current status
                if len(self.snapshots) > 1:
                    prev_snapshot = self.snapshots[-2]
                    memory_delta = snapshot.rss_mb - prev_snapshot.rss_mb
                    if abs(memory_delta) > 1.0:  # Only log significant changes
                        self.logger.debug(
                            f"Memory: {snapshot.rss_mb:.1f}MB "
                            f"(Δ{memory_delta:+.1f}MB), "
                            f"Objects: {snapshot.get_total_objects()}"
                        )
                
            except Exception as e:
                self.logger.error(f"Monitoring loop error: {e}")

    def _take_snapshot(self) -> MemorySnapshot:
        """Take detailed memory snapshot"""
        # Basic memory info
        memory_info = self.process.memory_info()
        memory_percent = self.process.memory_percent()
        virtual_memory = psutil.virtual_memory()
        
        # Garbage collection info
        gc_counts = {i: gc.get_count()[i] for i in range(3)}
        
        # Object counts by type
        object_counts = self._get_object_counts()
        
        # Tracemalloc top traces
        top_traces = []
        if self.enable_tracemalloc and tracemalloc.is_tracing():
            top_traces = self._get_top_memory_traces()
        
        return MemorySnapshot(
            timestamp=datetime.now(),
            rss_mb=memory_info.rss / 1024 / 1024,
            vms_mb=memory_info.vms / 1024 / 1024,
            peak_rss_mb=memory_info.peak_wset / 1024 / 1024 if hasattr(memory_info, 'peak_wset') else 0,
            available_mb=virtual_memory.available / 1024 / 1024,
            percent=memory_percent,
            swap_mb=virtual_memory.used / 1024 / 1024 if hasattr(virtual_memory, 'used') else 0,
            gc_counts=gc_counts,
            object_counts=object_counts,
            top_traces=top_traces
        )

    def _get_object_counts(self) -> Dict[str, int]:
        """Get count of objects by type"""
        counts = defaultdict(int)
        
        # Count all objects
        for obj in gc.get_objects():
            obj_type = type(obj).__name__
            counts[obj_type] += 1
        
        return dict(counts)

    def _get_top_memory_traces(self) -> List[Dict[str, Any]]:
        """Get top memory allocations from tracemalloc"""
        if not tracemalloc.is_tracing():
            return []
        
        try:
            snapshot = tracemalloc.take_snapshot()
            top_stats = snapshot.statistics('lineno')
            
            traces = []
            for stat in top_stats[:self.max_traces]:
                trace_info = {
                    'size_mb': stat.size / 1024 / 1024,
                    'count': stat.count,
                    'filename': stat.traceback.format()[-1] if stat.traceback else 'unknown',
                    'traceback': [str(frame) for frame in stat.traceback.format()] if stat.traceback else []
                }
                traces.append(trace_info)
            
            return traces
            
        except Exception as e:
            self.logger.error(f"Error getting memory traces: {e}")
            return []

    def _cleanup_old_snapshots(self):
        """Remove old snapshots beyond retention period"""
        cutoff_time = datetime.now() - self.snapshot_retention
        
        while self.snapshots and self.snapshots[0].timestamp < cutoff_time:
            self.snapshots.popleft()

    def _analyze_memory_patterns(self):
        """Analyze memory patterns for potential leaks"""
        if len(self.snapshots) < 5:  # Need at least 5 snapshots
            return
        
        recent_snapshots = list(self.snapshots)[-10:]  # Last 10 snapshots
        
        # Check for overall memory growth
        self._check_overall_growth(recent_snapshots)
        
        # Check for object count growth
        self._check_object_growth(recent_snapshots)
        
        # Check for suspicious patterns
        self._check_suspicious_patterns(recent_snapshots)

    def _check_overall_growth(self, snapshots: List[MemorySnapshot]):
        """Check for overall memory growth trend"""
        if len(snapshots) < 3:
            return
        
        memory_values = [s.rss_mb for s in snapshots]
        timestamps = [s.timestamp.timestamp() for s in snapshots]
        
        # Calculate growth rate (MB per hour)
        if len(memory_values) >= 2:
            time_diff_hours = (timestamps[-1] - timestamps[0]) / 3600
            if time_diff_hours > 0:
                memory_growth = memory_values[-1] - memory_values[0]
                growth_rate = memory_growth / time_diff_hours
                
                if growth_rate > self.growth_rate_threshold:
                    self.logger.warning(
                        f"High memory growth rate detected: "
                        f"{growth_rate:.1f} MB/hour "
                        f"(threshold: {self.growth_rate_threshold} MB/hour)"
                    )

    def _check_object_growth(self, snapshots: List[MemorySnapshot]):
        """Check for object count growth by type"""
        if len(snapshots) < 3:
            return
        
        # Analyze each object type
        first_snapshot = snapshots[0]
        last_snapshot = snapshots[-1]
        
        for obj_type in last_snapshot.object_counts:
            first_count = first_snapshot.object_counts.get(obj_type, 0)
            last_count = last_snapshot.object_counts[obj_type]
            
            if first_count > 0:
                growth_ratio = last_count / first_count
                if growth_ratio > 2.0 and last_count > 100:  # 100% growth and significant count
                    self.logger.warning(
                        f"Object type '{obj_type}' grew from {first_count} to {last_count} "
                        f"({growth_ratio:.1f}x growth)"
                    )

    def _check_suspicious_patterns(self, snapshots: List[MemorySnapshot]):
        """Check for suspicious memory patterns"""
        # Check for memory that never gets freed
        memory_values = [s.rss_mb for s in snapshots]
        
        # Check for consistently high memory with no drops
        if len(memory_values) >= 5:
            min_memory = min(memory_values)
            max_memory = max(memory_values)
            
            # If memory never drops below 90% of peak, it's suspicious
            if min_memory > max_memory * 0.9 and max_memory > 100:  # >100MB
                self.logger.warning(
                    f"Memory never significantly drops: "
                    f"min={min_memory:.1f}MB, max={max_memory:.1f}MB"
                )

    def _update_object_tracking(self):
        """Update object lifetime tracking"""
        current_time = datetime.now()
        
        # Clean up destroyed objects
        destroyed_objects = []
        for obj_id, lifetime in self.object_lifetimes.items():
            if not lifetime.is_alive and lifetime.destruction_time:
                # Keep for analysis but clean up old ones
                if current_time - lifetime.destruction_time > timedelta(hours=1):
                    destroyed_objects.append(obj_id)
        
        for obj_id in destroyed_objects:
            del self.object_lifetimes[obj_id]

    def track_object(self, obj: Any, category: str = "unknown"):
        """Track specific object for leak detection"""
        obj_id = id(obj)
        obj_type = f"{category}:{type(obj).__name__}"
        
        # Get creation traceback
        creation_traceback = traceback.format_stack()
        
        # Calculate object size
        size_bytes = sys.getsizeof(obj)
        
        # Create lifetime tracker
        lifetime = ObjectLifetime(
            object_type=obj_type,
            object_id=obj_id,
            created_at=datetime.now(),
            size_bytes=size_bytes,
            creation_traceback=creation_traceback,
            reference_count=sys.getrefcount(obj),
            last_accessed=datetime.now()
        )
        
        self.object_lifetimes[obj_id] = lifetime
        
        # Set up weak reference callback
        def cleanup_callback(ref):
            if obj_id in self.object_lifetimes:
                self.object_lifetimes[obj_id].mark_destroyed()
        
        try:
            weakref.ref(obj, cleanup_callback)
            self.tracked_objects.add(obj)
        except TypeError:
            # Object doesn't support weak references
            pass

    def detect_leaks(self) -> List[LeakSuspicion]:
        """Analyze current state and detect potential memory leaks"""
        suspicions = []
        
        if len(self.snapshots) < 5:
            return suspicions
        
        # Analyze object lifetimes
        current_time = datetime.now()
        object_stats = defaultdict(list)
        
        for lifetime in self.object_lifetimes.values():
            if lifetime.is_alive:
                object_stats[lifetime.object_type].append(lifetime)
        
        # Check each object type for suspicious patterns
        for obj_type, lifetimes in object_stats.items():
            if len(lifetimes) < 5:  # Need significant count
                continue
            
            # Calculate statistics
            total_size_mb = sum(lt.size_bytes for lt in lifetimes) / 1024 / 1024
            avg_lifetime_hours = statistics.mean([lt.lifetime_seconds / 3600 for lt in lifetimes])
            oldest_lifetime_hours = max([lt.lifetime_seconds / 3600 for lt in lifetimes])
            
            # Calculate growth rate
            recent_snapshots = list(self.snapshots)[-10:]
            growth_rate = self._calculate_growth_rate(obj_type, recent_snapshots)
            
            # Calculate suspicion score
            suspicion_score = self._calculate_suspicion_score(
                len(lifetimes), total_size_mb, growth_rate, avg_lifetime_hours, oldest_lifetime_hours
            )
            
            # If suspicious, create leak suspicion
            if suspicion_score > 0.7:  # 70% suspicion threshold
                evidence = []
                recommendations = []
                
                if len(lifetimes) > 100:
                    evidence.append(f"High instance count: {len(lifetimes)}")
                    recommendations.append("Review object creation and cleanup logic")
                
                if total_size_mb > 50:
                    evidence.append(f"High memory usage: {total_size_mb:.1f}MB")
                    recommendations.append("Implement object pooling or reuse")
                
                if growth_rate > 5:
                    evidence.append(f"High growth rate: {growth_rate:.1f} objects/hour")
                    recommendations.append("Add explicit cleanup in error paths")
                
                if avg_lifetime_hours > 2:
                    evidence.append(f"Long average lifetime: {avg_lifetime_hours:.1f} hours")
                    recommendations.append("Implement TTL-based cleanup")
                
                # Get sample tracebacks
                sample_tracebacks = [lt.creation_traceback for lt in lifetimes[:5]]
                
                suspicion = LeakSuspicion(
                    object_type=obj_type,
                    instance_count=len(lifetimes),
                    total_size_mb=total_size_mb,
                    growth_rate_per_hour=growth_rate,
                    avg_lifetime_hours=avg_lifetime_hours,
                    oldest_instance_hours=oldest_lifetime_hours,
                    suspicion_score=suspicion_score,
                    evidence=evidence,
                    recommendations=recommendations,
                    sample_tracebacks=sample_tracebacks
                )
                
                suspicions.append(suspicion)
        
        self.leak_suspicions = suspicions
        return suspicions

    def _calculate_growth_rate(self, obj_type: str, snapshots: List[MemorySnapshot]) -> float:
        """Calculate growth rate for specific object type"""
        if len(snapshots) < 2:
            return 0.0
        
        first_count = snapshots[0].object_counts.get(obj_type, 0)
        last_count = snapshots[-1].object_counts.get(obj_type, 0)
        
        time_diff_hours = (snapshots[-1].timestamp - snapshots[0].timestamp).total_seconds() / 3600
        
        if time_diff_hours > 0:
            return (last_count - first_count) / time_diff_hours
        
        return 0.0

    def _calculate_suspicion_score(
        self, 
        instance_count: int, 
        total_size_mb: float, 
        growth_rate: float, 
        avg_lifetime_hours: float, 
        oldest_lifetime_hours: float
    ) -> float:
        """Calculate suspicion score (0-1) for potential memory leak"""
        score = 0.0
        
        # Instance count factor
        if instance_count > 1000:
            score += 0.3
        elif instance_count > 100:
            score += 0.2
        elif instance_count > 50:
            score += 0.1
        
        # Memory size factor
        if total_size_mb > 100:
            score += 0.3
        elif total_size_mb > 50:
            score += 0.2
        elif total_size_mb > 10:
            score += 0.1
        
        # Growth rate factor
        if growth_rate > 20:
            score += 0.2
        elif growth_rate > 10:
            score += 0.15
        elif growth_rate > 5:
            score += 0.1
        
        # Lifetime factor
        if avg_lifetime_hours > 6:
            score += 0.2
        elif avg_lifetime_hours > 2:
            score += 0.15
        elif avg_lifetime_hours > 1:
            score += 0.1
        
        return min(score, 1.0)

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive memory leak detection report"""
        if not self.snapshots:
            return {"error": "No memory snapshots available"}
        
        current_snapshot = self.snapshots[-1]
        baseline_snapshot = self.baseline_memory or self.snapshots[0]
        
        # Detect current leaks
        current_leaks = self.detect_leaks()
        
        # Calculate overall statistics
        memory_growth_mb = current_snapshot.rss_mb - baseline_snapshot.rss_mb
        runtime_hours = (current_snapshot.timestamp - baseline_snapshot.timestamp).total_seconds() / 3600
        
        report = {
            "report_generated_at": datetime.now().isoformat(),
            "monitoring_duration_hours": runtime_hours,
            "snapshot_count": len(self.snapshots),
            
            "memory_summary": {
                "baseline_memory_mb": baseline_snapshot.rss_mb,
                "current_memory_mb": current_snapshot.rss_mb,
                "peak_memory_mb": max(s.rss_mb for s in self.snapshots),
                "memory_growth_mb": memory_growth_mb,
                "growth_rate_mb_per_hour": memory_growth_mb / runtime_hours if runtime_hours > 0 else 0
            },
            
            "object_summary": {
                "baseline_objects": baseline_snapshot.get_total_objects(),
                "current_objects": current_snapshot.get_total_objects(),
                "object_growth": current_snapshot.get_total_objects() - baseline_snapshot.get_total_objects(),
                "tracked_objects": len(self.object_lifetimes)
            },
            
            "leak_analysis": {
                "suspected_leaks": len(current_leaks),
                "high_suspicion_leaks": len([l for l in current_leaks if l.suspicion_score > 0.8]),
                "total_leaked_memory_mb": sum(l.total_size_mb for l in current_leaks),
                "leak_details": [asdict(leak) for leak in current_leaks]
            },
            
            "recommendations": self._generate_general_recommendations(current_leaks, memory_growth_mb, runtime_hours)
        }
        
        return report

    def _generate_general_recommendations(
        self, 
        leaks: List[LeakSuspicion], 
        memory_growth_mb: float, 
        runtime_hours: float
    ) -> List[str]:
        """Generate general recommendations for memory optimization"""
        recommendations = []
        
        if memory_growth_mb > 100:
            recommendations.append("High memory growth detected - review object lifecycle management")
        
        if len(leaks) > 5:
            recommendations.append("Multiple potential leaks detected - implement comprehensive cleanup strategy")
        
        if runtime_hours > 0 and memory_growth_mb / runtime_hours > 10:
            recommendations.append("Fast memory growth rate - add memory monitoring alerts")
        
        # High-priority leaks
        critical_leaks = [l for l in leaks if l.suspicion_score > 0.9]
        if critical_leaks:
            recommendations.append(f"Critical: {len(critical_leaks)} high-confidence leaks need immediate attention")
        
        # General recommendations
        if not recommendations:
            recommendations.append("Memory usage appears stable - continue monitoring")
        
        return recommendations

    def save_report(self, filename: Optional[str] = None) -> str:
        """Save memory leak detection report to file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"memory_leak_report_{timestamp}.json"
        
        report = self.generate_report()
        
        # Create reports directory
        reports_dir = Path("performance_reports")
        reports_dir.mkdir(exist_ok=True)
        
        report_path = reports_dir / filename
        
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        
        self.logger.info(f"Memory leak report saved to {report_path}")
        return str(report_path)

    def force_garbage_collection(self):
        """Force garbage collection and analyze results"""
        before_snapshot = self._take_snapshot()
        
        # Force full garbage collection
        collected = gc.collect()
        
        after_snapshot = self._take_snapshot()
        
        memory_freed = before_snapshot.rss_mb - after_snapshot.rss_mb
        
        self.logger.info(
            f"Garbage collection: collected {collected} objects, "
            f"freed {memory_freed:.1f}MB memory"
        )
        
        return {
            "objects_collected": collected,
            "memory_freed_mb": memory_freed,
            "before_memory_mb": before_snapshot.rss_mb,
            "after_memory_mb": after_snapshot.rss_mb
        }


# Decorator for automatic object tracking
def track_memory_usage(category: str = "unknown"):
    """Decorator to track memory usage of function results"""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            result = func(*args, **kwargs)
            
            # Get global detector if available
            if hasattr(wrapper, '_detector'):
                wrapper._detector.track_object(result, category)
            
            return result
        
        return wrapper
    return decorator


# Global detector instance
_global_detector: Optional[MemoryLeakDetector] = None

def get_leak_detector() -> MemoryLeakDetector:
    """Get global memory leak detector instance"""
    global _global_detector
    if _global_detector is None:
        _global_detector = MemoryLeakDetector()
    return _global_detector


if __name__ == "__main__":
    # Example usage and testing
    detector = MemoryLeakDetector(detection_interval_seconds=5)
    
    # Start monitoring
    detector.start_monitoring()
    
    try:
        # Simulate memory leaks for testing
        leaked_objects = []
        
        for i in range(100):
            # Simulate object creation that might leak
            obj = [f"data_{j}" for j in range(1000)]  # ~8KB object
            leaked_objects.append(obj)
            detector.track_object(obj, "test_object")
            
            time.sleep(0.1)
            
            # Every 20 iterations, analyze
            if i % 20 == 0:
                leaks = detector.detect_leaks()
                if leaks:
                    print(f"Detected {len(leaks)} potential leaks")
                    for leak in leaks[:3]:  # Show top 3
                        print(f"  - {leak.object_type}: {leak.instance_count} instances, "
                              f"{leak.total_size_mb:.1f}MB, score: {leak.suspicion_score:.2f}")
        
        # Generate final report
        report_path = detector.save_report()
        print(f"Final report saved to: {report_path}")
        
    finally:
        detector.stop_monitoring() 