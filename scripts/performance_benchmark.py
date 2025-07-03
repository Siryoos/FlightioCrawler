#!/usr/bin/env python3
"""
Performance Benchmarking Tool برای FlightioCrawler
این اسکریپت عملکرد پایگاه داده را تست و بنچمارک می‌کند
"""

import asyncio
import time
import statistics
import random
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import json
import argparse
from pathlib import Path
import psycopg2
from psycopg2.extras import RealDictCursor
import concurrent.futures
import threading
from contextlib import contextmanager
import sys
import os

# اضافه کردن path پروژه
sys.path.append(str(Path(__file__).parent.parent))

from config import config
from data_manager import DataManager
from monitoring.db_performance_monitor import DatabasePerformanceMonitor
import logging

# تنظیم logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@dataclass
class BenchmarkResult:
    """نتیجه یک تست benchmark"""
    test_name: str
    duration: float
    queries_per_second: float
    total_queries: int
    avg_response_time: float
    min_response_time: float
    max_response_time: float
    percentile_95: float
    success_rate: float
    error_count: int
    concurrent_users: int
    memory_usage: Optional[float] = None
    cpu_usage: Optional[float] = None

@dataclass
class BenchmarkConfig:
    """تنظیمات benchmark"""
    concurrent_users: int = 10
    test_duration: int = 60  # seconds
    queries_per_user: int = 100
    warm_up_time: int = 10  # seconds
    cool_down_time: int = 5  # seconds
    include_write_operations: bool = True
    include_complex_queries: bool = True
    
class DatabaseBenchmark:
    """کلاس اصلی برای benchmark پایگاه داده"""
    
    def __init__(self, config_obj: BenchmarkConfig):
        self.config = config_obj
        self.data_manager = DataManager()
        self.monitor = DatabasePerformanceMonitor()
        self.results: List[BenchmarkResult] = []
        self.sample_airports = ['THR', 'IKA', 'MHD', 'IST', 'DXB', 'LHR', 'CDG', 'FRA']
        self.sample_airlines = ['IR', 'W5', 'EP', 'TK', 'EK', 'QR', 'LH', 'AF']
        
    def generate_sample_data(self, count: int = 1000) -> None:
        """تولید داده‌های نمونه برای تست"""
        logger.info(f"تولید {count} رکورد داده نمونه...")
        
        sample_flights = []
        base_time = datetime.now() + timedelta(days=1)
        
        for i in range(count):
            origin = random.choice(self.sample_airports)
            destination = random.choice([a for a in self.sample_airports if a != origin])
            airline = random.choice(self.sample_airlines)
            
            departure_time = base_time + timedelta(
                days=random.randint(0, 30),
                hours=random.randint(0, 23),
                minutes=random.randint(0, 59)
            )
            
            flight_data = {
                'site_1': [{
                    'airline': airline,
                    'flight_number': f"{airline}{random.randint(100, 999)}",
                    'origin': origin,
                    'destination': destination,
                    'departure_time': departure_time.isoformat(),
                    'arrival_time': (departure_time + timedelta(hours=random.randint(1, 8))).isoformat(),
                    'price': random.uniform(100000, 5000000),
                    'currency': 'IRR',
                    'seat_class': random.choice(['economy', 'business', 'first']),
                    'aircraft_type': random.choice(['A320', 'B737', 'A380', 'B777']),
                    'duration_minutes': random.randint(60, 480),
                    'flight_type': 'scheduled',
                    'source_url': f'https://example.com/flight/{i}'
                }]
            }
            
            sample_flights.append(flight_data)
            
            # batch insert هر 100 رکورد
            if len(sample_flights) >= 100:
                self.data_manager.store_flights({'batch': [f for fd in sample_flights for f in fd['site_1']]})
                sample_flights = []
        
        # insert باقی‌مانده رکوردها
        if sample_flights:
            self.data_manager.store_flights({'batch': [f for fd in sample_flights for f in fd['site_1']]})
            
        logger.info("تولید داده‌های نمونه تکمیل شد")

    def run_simple_queries(self, user_id: int, queries_count: int) -> List[float]:
        """اجرای کوئری‌های ساده"""
        response_times = []
        
        for _ in range(queries_count):
            start_time = time.time()
            
            try:
                # کوئری ساده: جستجوی پروازها
                origin = random.choice(self.sample_airports)
                destination = random.choice([a for a in self.sample_airports if a != origin])
                
                with self.data_manager.get_session() as session:
                    from data_manager import Flight
                    flights = session.query(Flight).filter(
                        Flight.origin == origin,
                        Flight.destination == destination
                    ).limit(50).all()
                    
                response_time = time.time() - start_time
                response_times.append(response_time)
                
            except Exception as e:
                logger.error(f"خطا در کوئری ساده کاربر {user_id}: {e}")
                response_times.append(float('inf'))
                
        return response_times

    def run_complex_queries(self, user_id: int, queries_count: int) -> List[float]:
        """اجرای کوئری‌های پیچیده"""
        response_times = []
        
        for _ in range(queries_count):
            start_time = time.time()
            
            try:
                # کوئری پیچیده: آمار قیمت پروازها
                origin = random.choice(self.sample_airports)
                
                with self.data_manager.get_session() as session:
                    from data_manager import Flight
                    from sqlalchemy import func
                    
                    result = session.query(
                        func.avg(Flight.price).label('avg_price'),
                        func.min(Flight.price).label('min_price'),
                        func.max(Flight.price).label('max_price'),
                        func.count(Flight.id).label('flight_count')
                    ).filter(
                        Flight.origin == origin,
                        Flight.price > 0
                    ).first()
                    
                response_time = time.time() - start_time
                response_times.append(response_time)
                
            except Exception as e:
                logger.error(f"خطا در کوئری پیچیده کاربر {user_id}: {e}")
                response_times.append(float('inf'))
                
        return response_times

    def run_write_operations(self, user_id: int, operations_count: int) -> List[float]:
        """اجرای عملیات نوشتن"""
        response_times = []
        
        for _ in range(operations_count):
            start_time = time.time()
            
            try:
                # عملیات نوشتن: اضافه کردن search query
                origin = random.choice(self.sample_airports)
                destination = random.choice([a for a in self.sample_airports if a != origin])
                
                search_params = {
                    'origin': origin,
                    'destination': destination,
                    'departure_date': '2024-06-01',
                    'passengers': random.randint(1, 4),
                    'seat_class': 'economy'
                }
                
                self.data_manager.store_search_query(
                    search_params,
                    result_count=random.randint(0, 100),
                    search_duration=random.uniform(0.5, 3.0),
                    cached=random.choice([True, False])
                )
                
                response_time = time.time() - start_time
                response_times.append(response_time)
                
            except Exception as e:
                logger.error(f"خطا در عملیات نوشتن کاربر {user_id}: {e}")
                response_times.append(float('inf'))
                
        return response_times

    def run_user_simulation(self, user_id: int) -> Dict[str, List[float]]:
        """شبیه‌سازی یک کاربر"""
        logger.info(f"شروع شبیه‌سازی کاربر {user_id}")
        
        results = {
            'simple_queries': [],
            'complex_queries': [],
            'write_operations': []
        }
        
        queries_per_test = self.config.queries_per_user // 3
        
        # کوئری‌های ساده
        results['simple_queries'] = self.run_simple_queries(user_id, queries_per_test)
        
        # کوئری‌های پیچیده
        if self.config.include_complex_queries:
            results['complex_queries'] = self.run_complex_queries(user_id, queries_per_test)
        
        # عملیات نوشتن
        if self.config.include_write_operations:
            results['write_operations'] = self.run_write_operations(user_id, queries_per_test)
        
        logger.info(f"پایان شبیه‌سازی کاربر {user_id}")
        return results

    def calculate_benchmark_result(self, test_name: str, all_response_times: List[float]) -> BenchmarkResult:
        """محاسبه نتیجه benchmark"""
        # حذف response time های نامعتبر
        valid_times = [t for t in all_response_times if t != float('inf')]
        
        if not valid_times:
            return BenchmarkResult(
                test_name=test_name,
                duration=0,
                queries_per_second=0,
                total_queries=0,
                avg_response_time=0,
                min_response_time=0,
                max_response_time=0,
                percentile_95=0,
                success_rate=0,
                error_count=len(all_response_times),
                concurrent_users=self.config.concurrent_users
            )
        
        total_queries = len(all_response_times)
        error_count = len(all_response_times) - len(valid_times)
        success_rate = len(valid_times) / total_queries if total_queries > 0 else 0
        
        total_duration = sum(valid_times)
        avg_response_time = statistics.mean(valid_times)
        min_response_time = min(valid_times)
        max_response_time = max(valid_times)
        percentile_95 = statistics.quantiles(valid_times, n=20)[18] if len(valid_times) >= 20 else max_response_time
        
        queries_per_second = len(valid_times) / total_duration if total_duration > 0 else 0
        
        return BenchmarkResult(
            test_name=test_name,
            duration=total_duration,
            queries_per_second=queries_per_second,
            total_queries=total_queries,
            avg_response_time=avg_response_time,
            min_response_time=min_response_time,
            max_response_time=max_response_time,
            percentile_95=percentile_95,
            success_rate=success_rate,
            error_count=error_count,
            concurrent_users=self.config.concurrent_users
        )

    def run_benchmark(self) -> List[BenchmarkResult]:
        """اجرای benchmark اصلی"""
        logger.info("شروع benchmark پایگاه داده...")
        
        # warm-up
        logger.info("مرحله warm-up...")
        self.run_user_simulation(0)
        time.sleep(self.config.warm_up_time)
        
        # benchmark اصلی
        logger.info(f"شروع benchmark با {self.config.concurrent_users} کاربر همزمان...")
        
        all_results = {
            'simple_queries': [],
            'complex_queries': [],
            'write_operations': []
        }
        
        # اجرای همزمان کاربران
        with concurrent.futures.ThreadPoolExecutor(max_workers=self.config.concurrent_users) as executor:
            future_to_user = {
                executor.submit(self.run_user_simulation, i): i 
                for i in range(self.config.concurrent_users)
            }
            
            for future in concurrent.futures.as_completed(future_to_user):
                user_id = future_to_user[future]
                try:
                    user_results = future.result()
                    
                    # جمع‌آوری نتایج
                    for test_type, times in user_results.items():
                        all_results[test_type].extend(times)
                        
                except Exception as e:
                    logger.error(f"خطا در کاربر {user_id}: {e}")
        
        # محاسبه نتایج نهایی
        benchmark_results = []
        
        for test_type, response_times in all_results.items():
            if response_times:
                result = self.calculate_benchmark_result(test_type, response_times)
                benchmark_results.append(result)
                
        # cool-down
        logger.info("مرحله cool-down...")
        time.sleep(self.config.cool_down_time)
        
        self.results = benchmark_results
        logger.info("benchmark تکمیل شد")
        
        return benchmark_results

    def generate_report(self, output_file: Optional[str] = None) -> Dict[str, Any]:
        """تولید گزارش benchmark"""
        if not self.results:
            logger.warning("هیچ نتیجه‌ای برای گزارش وجود ندارد")
            return {}
        
        # گرفتن اطلاعات سیستم
        system_info = {
            'database_config': {
                'pool_size': config.DATABASE.POOL_SIZE,
                'max_overflow': config.DATABASE.MAX_OVERFLOW,
                'pool_timeout': config.DATABASE.POOL_TIMEOUT,
                'connection_string': config.DATABASE.connection_string
            },
            'benchmark_config': {
                'concurrent_users': self.config.concurrent_users,
                'test_duration': self.config.test_duration,
                'queries_per_user': self.config.queries_per_user,
                'include_write_operations': self.config.include_write_operations,
                'include_complex_queries': self.config.include_complex_queries
            }
        }
        
        # گرفتن اطلاعات performance
        performance_snapshot = self.monitor.get_performance_snapshot()
        connection_pool_status = self.data_manager.get_connection_pool_status()
        
        # محاسبه آمار کلی
        total_queries = sum(r.total_queries for r in self.results)
        avg_qps = sum(r.queries_per_second for r in self.results) / len(self.results)
        overall_success_rate = sum(r.success_rate * r.total_queries for r in self.results) / total_queries if total_queries > 0 else 0
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'system_info': system_info,
            'performance_snapshot': performance_snapshot.__dict__,
            'connection_pool_status': connection_pool_status,
            'benchmark_results': [r.__dict__ for r in self.results],
            'summary': {
                'total_queries': total_queries,
                'average_qps': avg_qps,
                'overall_success_rate': overall_success_rate,
                'total_errors': sum(r.error_count for r in self.results),
                'test_categories': len(self.results)
            },
            'recommendations': self._generate_recommendations()
        }
        
        # ذخیره گزارش
        if output_file:
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            logger.info(f"گزارش در {output_file} ذخیره شد")
        
        return report

    def _generate_recommendations(self) -> List[str]:
        """تولید پیشنهادات بهبود عملکرد"""
        recommendations = []
        
        for result in self.results:
            if result.avg_response_time > 1.0:
                recommendations.append(f"زمان پاسخ {result.test_name} بالا است ({result.avg_response_time:.2f}s) - بررسی indexes")
            
            if result.success_rate < 0.95:
                recommendations.append(f"نرخ موفقیت {result.test_name} پایین است ({result.success_rate:.2%}) - بررسی خطاها")
            
            if result.queries_per_second < 10:
                recommendations.append(f"QPS {result.test_name} پایین است ({result.queries_per_second:.1f}) - بهینه‌سازی کوئری‌ها")
        
        # پیشنهادات کلی
        connection_pool_status = self.data_manager.get_connection_pool_status()
        if connection_pool_status.get('checked_out', 0) > connection_pool_status.get('pool_size', 0) * 0.8:
            recommendations.append("استفاده از connection pool بالا است - افزایش pool size")
        
        return recommendations

    def print_summary(self):
        """چاپ خلاصه نتایج"""
        if not self.results:
            print("هیچ نتیجه‌ای برای نمایش وجود ندارد")
            return
        
        print("\n" + "="*80)
        print("خلاصه نتایج Benchmark پایگاه داده")
        print("="*80)
        
        for result in self.results:
            print(f"\n📊 {result.test_name.upper()}:")
            print(f"   📈 کل کوئری‌ها: {result.total_queries}")
            print(f"   ⚡ کوئری در ثانیه: {result.queries_per_second:.1f}")
            print(f"   ⏱️  متوسط زمان پاسخ: {result.avg_response_time:.3f}s")
            print(f"   📉 کمترین زمان: {result.min_response_time:.3f}s")
            print(f"   📈 بیشترین زمان: {result.max_response_time:.3f}s") 
            print(f"   🎯 95% percentile: {result.percentile_95:.3f}s")
            print(f"   ✅ نرخ موفقیت: {result.success_rate:.2%}")
            print(f"   ❌ تعداد خطاها: {result.error_count}")
        
        print(f"\n🔧 تنظیمات:")
        print(f"   👥 کاربران همزمان: {self.config.concurrent_users}")
        print(f"   🔄 کوئری هر کاربر: {self.config.queries_per_user}")
        
        # پیشنهادات
        recommendations = self._generate_recommendations()
        if recommendations:
            print(f"\n💡 پیشنهادات:")
            for i, rec in enumerate(recommendations, 1):
                print(f"   {i}. {rec}")
        
        print("="*80)


def main():
    """تابع اصلی"""
    parser = argparse.ArgumentParser(description='Database Performance Benchmark')
    parser.add_argument('--users', type=int, default=10, help='تعداد کاربران همزمان')
    parser.add_argument('--queries', type=int, default=100, help='تعداد کوئری هر کاربر')
    parser.add_argument('--duration', type=int, default=60, help='مدت زمان تست (ثانیه)')
    parser.add_argument('--output', type=str, help='فایل خروجی گزارش')
    parser.add_argument('--generate-data', action='store_true', help='تولید داده‌های نمونه')
    parser.add_argument('--data-count', type=int, default=1000, help='تعداد داده‌های نمونه')
    parser.add_argument('--no-writes', action='store_true', help='عدم اجرای عملیات نوشتن')
    parser.add_argument('--no-complex', action='store_true', help='عدم اجرای کوئری‌های پیچیده')
    
    args = parser.parse_args()
    
    # تنظیمات benchmark
    benchmark_config = BenchmarkConfig(
        concurrent_users=args.users,
        test_duration=args.duration,
        queries_per_user=args.queries,
        include_write_operations=not args.no_writes,
        include_complex_queries=not args.no_complex
    )
    
    # ایجاد benchmark
    benchmark = DatabaseBenchmark(benchmark_config)
    
    try:
        # تولید داده‌های نمونه
        if args.generate_data:
            benchmark.generate_sample_data(args.data_count)
        
        # اجرای benchmark
        results = benchmark.run_benchmark()
        
        # نمایش نتایج
        benchmark.print_summary()
        
        # تولید گزارش
        report = benchmark.generate_report(args.output)
        
        if args.output:
            print(f"\n📄 گزارش کامل در {args.output} ذخیره شد")
        
    except KeyboardInterrupt:
        logger.info("benchmark توسط کاربر متوقف شد")
    except Exception as e:
        logger.error(f"خطا در اجرای benchmark: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()