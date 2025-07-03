"""
Database Performance Monitor
تحلیل کننده performance پایگاه داده و slow queries
"""

import logging
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import json
from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd
from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool
from config import config

logger = logging.getLogger(__name__)

@dataclass
class QueryPerformanceMetrics:
    """کلاس برای ذخیره metrics عملکرد کوئری‌ها"""
    query_hash: str
    query_text: str
    calls: int
    total_time: float
    avg_time: float
    min_time: float
    max_time: float
    stddev_time: float
    rows_examined: int
    rows_returned: int
    database_name: str
    user_name: str
    first_seen: datetime
    last_seen: datetime

@dataclass
class DatabasePerformanceSnapshot:
    """کلاس برای ذخیره snapshot عملکرد پایگاه داده"""
    timestamp: datetime
    active_connections: int
    idle_connections: int
    total_connections: int
    database_size: int
    cache_hit_ratio: float
    slow_queries_count: int
    average_query_time: float
    deadlocks_count: int
    temp_files_count: int
    temp_bytes: int

class DatabasePerformanceMonitor:
    """کلاس اصلی برای monitoring عملکرد پایگاه داده"""
    
    def __init__(self, connection_string: str = None):
        """
        مقداردهی اولیه monitor
        
        Args:
            connection_string: رشته اتصال به پایگاه داده
        """
        if connection_string:
            self.connection_string = connection_string
        else:
            self.connection_string = f"postgresql://{config.DATABASE.USER}:{config.DATABASE.PASSWORD}@{config.DATABASE.HOST}:{config.DATABASE.PORT}/{config.DATABASE.NAME}"
        
        self.engine = create_engine(
            self.connection_string,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        
        self.slow_query_threshold = 1000  # milliseconds
        self.performance_history = []
        
    def setup_monitoring(self) -> None:
        """راه‌اندازی monitoring extensions و functions"""
        setup_queries = [
            # فعال کردن pg_stat_statements برای tracking کوئری‌ها
            "CREATE EXTENSION IF NOT EXISTS pg_stat_statements;",
            
            # ایجاد function برای تحلیل slow queries
            """
            CREATE OR REPLACE FUNCTION analyze_slow_queries(threshold_ms INTEGER DEFAULT 1000)
            RETURNS TABLE (
                query_hash TEXT,
                query_text TEXT,
                calls BIGINT,
                total_time DOUBLE PRECISION,
                avg_time DOUBLE PRECISION,
                min_time DOUBLE PRECISION,
                max_time DOUBLE PRECISION,
                stddev_time DOUBLE PRECISION,
                rows_examined BIGINT,
                rows_returned BIGINT
            ) AS $$
            BEGIN
                RETURN QUERY
                SELECT 
                    md5(pss.query) as query_hash,
                    pss.query as query_text,
                    pss.calls,
                    pss.total_exec_time as total_time,
                    pss.mean_exec_time as avg_time,
                    pss.min_exec_time as min_time,
                    pss.max_exec_time as max_time,
                    pss.stddev_exec_time as stddev_time,
                    pss.rows as rows_examined,
                    pss.rows as rows_returned
                FROM pg_stat_statements pss
                WHERE pss.mean_exec_time > threshold_ms
                ORDER BY pss.mean_exec_time DESC;
            END;
            $$ LANGUAGE plpgsql;
            """,
            
            # ایجاد view برای monitoring آماری
            """
            CREATE OR REPLACE VIEW database_performance_overview AS
            SELECT 
                (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
                (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle') as idle_connections,
                (SELECT count(*) FROM pg_stat_activity) as total_connections,
                (SELECT pg_database_size(current_database())) as database_size,
                (SELECT round(blks_hit::numeric/(blks_hit + blks_read) * 100, 2) 
                 FROM pg_stat_database WHERE datname = current_database()) as cache_hit_ratio,
                (SELECT count(*) FROM pg_stat_statements WHERE mean_exec_time > 1000) as slow_queries_count,
                (SELECT round(avg(mean_exec_time), 2) FROM pg_stat_statements) as average_query_time,
                (SELECT deadlocks FROM pg_stat_database WHERE datname = current_database()) as deadlocks_count,
                (SELECT temp_files FROM pg_stat_database WHERE datname = current_database()) as temp_files_count,
                (SELECT temp_bytes FROM pg_stat_database WHERE datname = current_database()) as temp_bytes;
            """,
            
            # ایجاد جدول برای ذخیره performance history
            """
            CREATE TABLE IF NOT EXISTS performance_history (
                id SERIAL PRIMARY KEY,
                timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                active_connections INTEGER,
                idle_connections INTEGER,
                total_connections INTEGER,
                database_size BIGINT,
                cache_hit_ratio DECIMAL(5,2),
                slow_queries_count INTEGER,
                average_query_time DECIMAL(10,2),
                deadlocks_count INTEGER,
                temp_files_count INTEGER,
                temp_bytes BIGINT,
                metadata JSONB
            );
            """,
            
            # ایجاد index برای performance_history
            "CREATE INDEX IF NOT EXISTS idx_performance_history_timestamp ON performance_history(timestamp DESC);",
            
            # ایجاد function برای automatic cleanup
            """
            CREATE OR REPLACE FUNCTION cleanup_old_performance_data()
            RETURNS void AS $$
            BEGIN
                DELETE FROM performance_history 
                WHERE timestamp < NOW() - INTERVAL '30 days';
                
                -- Reset pg_stat_statements اگر خیلی بزرگ شد
                IF (SELECT count(*) FROM pg_stat_statements) > 10000 THEN
                    PERFORM pg_stat_statements_reset();
                END IF;
            END;
            $$ LANGUAGE plpgsql;
            """,
        ]
        
        with self.engine.connect() as conn:
            for query in setup_queries:
                try:
                    conn.execute(text(query))
                    conn.commit()
                except Exception as e:
                    logger.warning(f"خطا در اجرای کوئری setup: {e}")
                    
    def analyze_slow_queries(self, threshold_ms: int = 1000) -> List[QueryPerformanceMetrics]:
        """
        تحلیل کوئری‌های کند
        
        Args:
            threshold_ms: آستانه زمانی به میلی‌ثانیه
            
        Returns:
            لیست کوئری‌های کند با metrics
        """
        query = """
        SELECT 
            md5(pss.query) as query_hash,
            pss.query as query_text,
            pss.calls,
            pss.total_exec_time as total_time,
            pss.mean_exec_time as avg_time,
            pss.min_exec_time as min_time,
            pss.max_exec_time as max_time,
            pss.stddev_exec_time as stddev_time,
            pss.rows as rows_examined,
            pss.rows as rows_returned,
            current_database() as database_name,
            pss.userid::regrole as user_name,
            NOW() as first_seen,
            NOW() as last_seen
        FROM pg_stat_statements pss
        WHERE pss.mean_exec_time > :threshold
        ORDER BY pss.mean_exec_time DESC
        LIMIT 50;
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"threshold": threshold_ms})
                slow_queries = []
                
                for row in result:
                    metrics = QueryPerformanceMetrics(
                        query_hash=row.query_hash,
                        query_text=row.query_text[:500],  # محدود کردن طول کوئری
                        calls=row.calls,
                        total_time=row.total_time,
                        avg_time=row.avg_time,
                        min_time=row.min_time,
                        max_time=row.max_time,
                        stddev_time=row.stddev_time or 0,
                        rows_examined=row.rows_examined or 0,
                        rows_returned=row.rows_returned or 0,
                        database_name=row.database_name,
                        user_name=str(row.user_name),
                        first_seen=row.first_seen,
                        last_seen=row.last_seen
                    )
                    slow_queries.append(metrics)
                
                return slow_queries
                
        except Exception as e:
            logger.error(f"خطا در تحلیل slow queries: {e}")
            return []
            
    def get_performance_snapshot(self) -> DatabasePerformanceSnapshot:
        """
        گرفتن snapshot فعلی از عملکرد پایگاه داده
        
        Returns:
            DatabasePerformanceSnapshot
        """
        query = """
        SELECT 
            (SELECT count(*) FROM pg_stat_activity WHERE state = 'active') as active_connections,
            (SELECT count(*) FROM pg_stat_activity WHERE state = 'idle') as idle_connections,
            (SELECT count(*) FROM pg_stat_activity) as total_connections,
            (SELECT pg_database_size(current_database())) as database_size,
            (SELECT CASE 
                WHEN blks_hit + blks_read = 0 THEN 0
                ELSE round(blks_hit::numeric/(blks_hit + blks_read) * 100, 2)
            END FROM pg_stat_database WHERE datname = current_database()) as cache_hit_ratio,
            (SELECT count(*) FROM pg_stat_statements WHERE mean_exec_time > :threshold) as slow_queries_count,
            (SELECT COALESCE(round(avg(mean_exec_time), 2), 0) FROM pg_stat_statements) as average_query_time,
            (SELECT COALESCE(deadlocks, 0) FROM pg_stat_database WHERE datname = current_database()) as deadlocks_count,
            (SELECT COALESCE(temp_files, 0) FROM pg_stat_database WHERE datname = current_database()) as temp_files_count,
            (SELECT COALESCE(temp_bytes, 0) FROM pg_stat_database WHERE datname = current_database()) as temp_bytes;
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"threshold": self.slow_query_threshold})
                row = result.fetchone()
                
                if row:
                    return DatabasePerformanceSnapshot(
                        timestamp=datetime.now(),
                        active_connections=row.active_connections or 0,
                        idle_connections=row.idle_connections or 0,
                        total_connections=row.total_connections or 0,
                        database_size=row.database_size or 0,
                        cache_hit_ratio=float(row.cache_hit_ratio or 0),
                        slow_queries_count=row.slow_queries_count or 0,
                        average_query_time=float(row.average_query_time or 0),
                        deadlocks_count=row.deadlocks_count or 0,
                        temp_files_count=row.temp_files_count or 0,
                        temp_bytes=row.temp_bytes or 0
                    )
                else:
                    return DatabasePerformanceSnapshot(
                        timestamp=datetime.now(),
                        active_connections=0,
                        idle_connections=0,
                        total_connections=0,
                        database_size=0,
                        cache_hit_ratio=0.0,
                        slow_queries_count=0,
                        average_query_time=0.0,
                        deadlocks_count=0,
                        temp_files_count=0,
                        temp_bytes=0
                    )
                    
        except Exception as e:
            logger.error(f"خطا در گرفتن performance snapshot: {e}")
            return DatabasePerformanceSnapshot(
                timestamp=datetime.now(),
                active_connections=0,
                idle_connections=0,
                total_connections=0,
                database_size=0,
                cache_hit_ratio=0.0,
                slow_queries_count=0,
                average_query_time=0.0,
                deadlocks_count=0,
                temp_files_count=0,
                temp_bytes=0
            )
    
    def store_performance_snapshot(self, snapshot: DatabasePerformanceSnapshot) -> None:
        """
        ذخیره snapshot عملکرد در پایگاه داده
        
        Args:
            snapshot: DatabasePerformanceSnapshot
        """
        query = """
        INSERT INTO performance_history (
            active_connections, idle_connections, total_connections,
            database_size, cache_hit_ratio, slow_queries_count,
            average_query_time, deadlocks_count, temp_files_count, temp_bytes,
            metadata
        ) VALUES (
            :active_connections, :idle_connections, :total_connections,
            :database_size, :cache_hit_ratio, :slow_queries_count,
            :average_query_time, :deadlocks_count, :temp_files_count, :temp_bytes,
            :metadata
        );
        """
        
        try:
            with self.engine.connect() as conn:
                conn.execute(text(query), {
                    "active_connections": snapshot.active_connections,
                    "idle_connections": snapshot.idle_connections,
                    "total_connections": snapshot.total_connections,
                    "database_size": snapshot.database_size,
                    "cache_hit_ratio": snapshot.cache_hit_ratio,
                    "slow_queries_count": snapshot.slow_queries_count,
                    "average_query_time": snapshot.average_query_time,
                    "deadlocks_count": snapshot.deadlocks_count,
                    "temp_files_count": snapshot.temp_files_count,
                    "temp_bytes": snapshot.temp_bytes,
                    "metadata": json.dumps({"timestamp": snapshot.timestamp.isoformat()})
                })
                conn.commit()
                
        except Exception as e:
            logger.error(f"خطا در ذخیره performance snapshot: {e}")
            
    def get_performance_trends(self, hours: int = 24) -> List[Dict[str, Any]]:
        """
        گرفتن trend عملکرد در چند ساعت گذشته
        
        Args:
            hours: تعداد ساعات گذشته
            
        Returns:
            لیست dictionaries حاوی trend data
        """
        query = """
        SELECT 
            timestamp,
            active_connections,
            total_connections,
            cache_hit_ratio,
            slow_queries_count,
            average_query_time,
            database_size
        FROM performance_history
        WHERE timestamp > NOW() - INTERVAL '%s hours'
        ORDER BY timestamp;
        """ % hours
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query))
                trends = []
                
                for row in result:
                    trends.append({
                        "timestamp": row.timestamp.isoformat(),
                        "active_connections": row.active_connections,
                        "total_connections": row.total_connections,
                        "cache_hit_ratio": float(row.cache_hit_ratio or 0),
                        "slow_queries_count": row.slow_queries_count,
                        "average_query_time": float(row.average_query_time or 0),
                        "database_size": row.database_size
                    })
                
                return trends
                
        except Exception as e:
            logger.error(f"خطا در گرفتن performance trends: {e}")
            return []
            
    def generate_performance_report(self) -> Dict[str, Any]:
        """
        تولید گزارش جامع عملکرد
        
        Returns:
            Dictionary حاوی گزارش کامل
        """
        current_snapshot = self.get_performance_snapshot()
        slow_queries = self.analyze_slow_queries()
        trends = self.get_performance_trends(24)
        
        # محاسبه آمار کلی
        total_slow_queries = len(slow_queries)
        avg_query_time = current_snapshot.average_query_time
        cache_hit_ratio = current_snapshot.cache_hit_ratio
        
        # تشخیص مشکلات
        issues = []
        if cache_hit_ratio < 95:
            issues.append(f"نرخ cache hit پایین است: {cache_hit_ratio}%")
        if total_slow_queries > 10:
            issues.append(f"تعداد کوئری‌های کند زیاد است: {total_slow_queries}")
        if current_snapshot.total_connections > 50:
            issues.append(f"تعداد connection‌ها زیاد است: {current_snapshot.total_connections}")
        if avg_query_time > 100:
            issues.append(f"متوسط زمان کوئری بالا است: {avg_query_time}ms")
            
        # پیشنهادات بهبود
        recommendations = []
        if cache_hit_ratio < 95:
            recommendations.append("افزایش shared_buffers در PostgreSQL")
        if total_slow_queries > 10:
            recommendations.append("بررسی و بهینه‌سازی کوئری‌های کند")
        if current_snapshot.total_connections > 50:
            recommendations.append("استفاده از connection pooling")
            
        return {
            "timestamp": datetime.now().isoformat(),
            "current_snapshot": asdict(current_snapshot),
            "slow_queries": [asdict(q) for q in slow_queries[:10]],  # فقط 10 کوئری اول
            "trends": trends,
            "summary": {
                "total_slow_queries": total_slow_queries,
                "average_query_time": avg_query_time,
                "cache_hit_ratio": cache_hit_ratio,
                "active_connections": current_snapshot.active_connections,
                "database_size_mb": current_snapshot.database_size / (1024 * 1024)
            },
            "issues": issues,
            "recommendations": recommendations
        }
        
    def optimize_queries(self, query_hashes: List[str]) -> List[Dict[str, Any]]:
        """
        تحلیل و ارائه پیشنهادات بهینه‌سازی برای کوئری‌های مشخص
        
        Args:
            query_hashes: لیست hash کوئری‌ها
            
        Returns:
            لیست پیشنهادات بهینه‌سازی
        """
        optimizations = []
        
        for query_hash in query_hashes:
            # گرفتن اطلاعات کوئری
            query_info = self._get_query_info(query_hash)
            if not query_info:
                continue
                
            # تحلیل execution plan
            execution_plan = self._analyze_execution_plan(query_info['query_text'])
            
            # ارائه پیشنهادات
            suggestions = self._generate_optimization_suggestions(query_info, execution_plan)
            
            optimizations.append({
                "query_hash": query_hash,
                "query_text": query_info['query_text'][:200],
                "current_performance": query_info,
                "execution_plan": execution_plan,
                "suggestions": suggestions
            })
            
        return optimizations
        
    def _get_query_info(self, query_hash: str) -> Optional[Dict[str, Any]]:
        """گرفتن اطلاعات کوئری از pg_stat_statements"""
        query = """
        SELECT 
            query,
            calls,
            total_exec_time,
            mean_exec_time,
            rows
        FROM pg_stat_statements 
        WHERE md5(query) = :query_hash;
        """
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(query), {"query_hash": query_hash})
                row = result.fetchone()
                
                if row:
                    return {
                        "query_text": row.query,
                        "calls": row.calls,
                        "total_time": row.total_exec_time,
                        "avg_time": row.mean_exec_time,
                        "rows": row.rows
                    }
                    
        except Exception as e:
            logger.error(f"خطا در گرفتن اطلاعات کوئری: {e}")
            
        return None
        
    def _analyze_execution_plan(self, query_text: str) -> Dict[str, Any]:
        """تحلیل execution plan کوئری"""
        explain_query = f"EXPLAIN (FORMAT JSON, ANALYZE, BUFFERS) {query_text}"
        
        try:
            with self.engine.connect() as conn:
                result = conn.execute(text(explain_query))
                plan_data = result.fetchone()[0]
                
                return {
                    "plan": plan_data,
                    "total_cost": plan_data[0]["Plan"]["Total Cost"],
                    "execution_time": plan_data[0].get("Execution Time", 0),
                    "planning_time": plan_data[0].get("Planning Time", 0)
                }
                
        except Exception as e:
            logger.error(f"خطا در تحلیل execution plan: {e}")
            return {}
            
    def _generate_optimization_suggestions(self, query_info: Dict[str, Any], execution_plan: Dict[str, Any]) -> List[str]:
        """تولید پیشنهادات بهینه‌سازی"""
        suggestions = []
        
        # بررسی زمان اجرا
        if query_info.get("avg_time", 0) > 1000:
            suggestions.append("زمان اجرای کوئری بالا است - بررسی indexes")
            
        # بررسی تعداد rows
        if query_info.get("rows", 0) > 10000:
            suggestions.append("تعداد rows بررسی شده زیاد است - استفاده از LIMIT")
            
        # بررسی execution plan
        if execution_plan.get("total_cost", 0) > 10000:
            suggestions.append("هزینه اجرای کوئری بالا است - بررسی join conditions")
            
        # بررسی Seq Scan
        plan_text = str(execution_plan.get("plan", ""))
        if "Seq Scan" in plan_text:
            suggestions.append("استفاده از Seq Scan - اضافه کردن index مناسب")
            
        return suggestions
        
    def cleanup_old_data(self, days: int = 30) -> None:
        """پاکسازی داده‌های قدیمی"""
        queries = [
            f"DELETE FROM performance_history WHERE timestamp < NOW() - INTERVAL '{days} days';",
            "SELECT pg_stat_statements_reset();"
        ]
        
        try:
            with self.engine.connect() as conn:
                for query in queries:
                    conn.execute(text(query))
                conn.commit()
                logger.info(f"پاکسازی داده‌های قدیمی‌تر از {days} روز انجام شد")
                
        except Exception as e:
            logger.error(f"خطا در پاکسازی داده‌های قدیمی: {e}")

# تابع کمکی برای راه‌اندازی monitoring
def setup_database_monitoring():
    """راه‌اندازی monitoring پایگاه داده"""
    monitor = DatabasePerformanceMonitor()
    monitor.setup_monitoring()
    return monitor

# تابع کمکی برای گرفتن گزارش سریع
def get_quick_performance_report():
    """گرفتن گزارش سریع عملکرد"""
    monitor = DatabasePerformanceMonitor()
    return monitor.generate_performance_report()

if __name__ == "__main__":
    # تست monitor
    monitor = DatabasePerformanceMonitor()
    monitor.setup_monitoring()
    
    # گرفتن گزارش
    report = monitor.generate_performance_report()
    print(json.dumps(report, indent=2, ensure_ascii=False))