#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Memory Health Check Endpoint
نقطه پایانی بررسی سلامت حافظه

این ماژول یک endpoint HTTP برای بررسی وضعیت نظارت حافظه فراهم می‌کند
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn
from monitoring.production_memory_monitor import ProductionMemoryMonitor
import psutil
import gc

# Data Models
class HealthStatus(BaseModel):
    status: str
    timestamp: datetime
    uptime_seconds: int
    monitoring_active: bool
    memory_usage_mb: float
    memory_percentage: float
    swap_usage_percentage: float
    active_alerts: int
    total_alerts: int
    last_check: Optional[datetime]

class MemoryMetricsResponse(BaseModel):
    timestamp: datetime
    rss_mb: float
    vms_mb: float
    percent: float
    available_mb: float
    total_mb: float
    swap_used_mb: float
    swap_percent: float
    gc_collections: int
    gc_objects: int

class AlertSummary(BaseModel):
    total_alerts: int
    active_alerts: int
    resolved_alerts: int
    by_severity: Dict[str, int]
    by_component: Dict[str, int]
    latest_alert: Optional[Dict[str, Any]]

class MemoryHealthAPI:
    """API برای بررسی سلامت حافظه"""
    
    def __init__(self, monitor: ProductionMemoryMonitor):
        self.monitor = monitor
        self.app = FastAPI(
            title="Memory Health Check API",
            description="API برای نظارت سلامت حافظه سیستم Flight Crawler",
            version="1.0.0"
        )
        self.start_time = datetime.now()
        self.logger = logging.getLogger(__name__)
        
        # Setup routes
        self._setup_routes()
    
    def _setup_routes(self):
        """راه‌اندازی routes"""
        
        @self.app.get("/health", response_model=HealthStatus)
        async def health_check():
            """بررسی سلامت کلی سیستم"""
            try:
                # Get latest metrics
                latest_metrics = None
                if self.monitor.metrics_history:
                    latest_metrics = self.monitor.metrics_history[-1]
                
                # Calculate uptime
                uptime = (datetime.now() - self.start_time).total_seconds()
                
                # Determine status
                status = "healthy"
                if len(self.monitor.active_alerts) > 0:
                    critical_alerts = [
                        alert for alert in self.monitor.active_alerts.values()
                        if alert.severity in ['critical', 'emergency']
                    ]
                    if critical_alerts:
                        status = "critical"
                    else:
                        status = "warning"
                
                return HealthStatus(
                    status=status,
                    timestamp=datetime.now(),
                    uptime_seconds=int(uptime),
                    monitoring_active=self.monitor.running,
                    memory_usage_mb=latest_metrics.rss_mb if latest_metrics else 0,
                    memory_percentage=latest_metrics.percent if latest_metrics else 0,
                    swap_usage_percentage=latest_metrics.swap_percent if latest_metrics else 0,
                    active_alerts=len(self.monitor.active_alerts),
                    total_alerts=len(self.monitor.alerts_history),
                    last_check=latest_metrics.timestamp if latest_metrics else None
                )
                
            except Exception as e:
                self.logger.error(f"Error in health check: {e}")
                raise HTTPException(status_code=500, detail="خطا در بررسی سلامت سیستم")
        
        @self.app.get("/health/memory", response_model=MemoryMetricsResponse)
        async def memory_health():
            """بررسی تفصیلی سلامت حافظه"""
            try:
                # Get or collect fresh metrics
                if self.monitor.metrics_history:
                    latest_metrics = self.monitor.metrics_history[-1]
                else:
                    latest_metrics = self.monitor.collect_metrics()
                
                if not latest_metrics:
                    raise HTTPException(status_code=500, detail="امکان جمع‌آوری metrics وجود ندارد")
                
                return MemoryMetricsResponse(
                    timestamp=latest_metrics.timestamp,
                    rss_mb=latest_metrics.rss_mb,
                    vms_mb=latest_metrics.vms_mb,
                    percent=latest_metrics.percent,
                    available_mb=latest_metrics.available_mb,
                    total_mb=latest_metrics.total_mb,
                    swap_used_mb=latest_metrics.swap_used_mb,
                    swap_percent=latest_metrics.swap_percent,
                    gc_collections=latest_metrics.gc_collections,
                    gc_objects=latest_metrics.gc_objects
                )
                
            except Exception as e:
                self.logger.error(f"Error in memory health check: {e}")
                raise HTTPException(status_code=500, detail="خطا در بررسی سلامت حافظه")
        
        @self.app.get("/health/alerts", response_model=AlertSummary)
        async def alerts_summary(hours: int = Query(24, ge=1, le=168)):
            """خلاصه هشدارها"""
            try:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                recent_alerts = [
                    alert for alert in self.monitor.alerts_history
                    if alert.timestamp >= cutoff_time
                ]
                
                # Summarize by severity
                by_severity = {}
                for alert in recent_alerts:
                    by_severity[alert.severity] = by_severity.get(alert.severity, 0) + 1
                
                # Summarize by component
                by_component = {}
                for alert in recent_alerts:
                    by_component[alert.component] = by_component.get(alert.component, 0) + 1
                
                # Get latest alert
                latest_alert = None
                if recent_alerts:
                    latest = recent_alerts[-1]
                    latest_alert = {
                        "timestamp": latest.timestamp.isoformat(),
                        "severity": latest.severity,
                        "component": latest.component,
                        "message": latest.message,
                        "resolved": latest.resolved
                    }
                
                return AlertSummary(
                    total_alerts=len(recent_alerts),
                    active_alerts=len(self.monitor.active_alerts),
                    resolved_alerts=len([a for a in recent_alerts if a.resolved]),
                    by_severity=by_severity,
                    by_component=by_component,
                    latest_alert=latest_alert
                )
                
            except Exception as e:
                self.logger.error(f"Error in alerts summary: {e}")
                raise HTTPException(status_code=500, detail="خطا در خلاصه هشدارها")
        
        @self.app.get("/health/metrics/history")
        async def metrics_history(hours: int = Query(1, ge=1, le=24)):
            """تارخچه metrics"""
            try:
                cutoff_time = datetime.now() - timedelta(hours=hours)
                recent_metrics = [
                    {
                        "timestamp": metrics.timestamp.isoformat(),
                        "rss_mb": metrics.rss_mb,
                        "percent": metrics.percent,
                        "swap_percent": metrics.swap_percent,
                        "gc_objects": metrics.gc_objects
                    }
                    for metrics in self.monitor.metrics_history
                    if metrics.timestamp >= cutoff_time
                ]
                
                return {"metrics": recent_metrics, "count": len(recent_metrics)}
                
            except Exception as e:
                self.logger.error(f"Error in metrics history: {e}")
                raise HTTPException(status_code=500, detail="خطا در تاریخچه metrics")
        
        @self.app.post("/health/actions/gc")
        async def force_garbage_collection():
            """اجبار garbage collection"""
            try:
                before_objects = len(gc.get_objects())
                collected = gc.collect()
                after_objects = len(gc.get_objects())
                
                return {
                    "success": True,
                    "collected_objects": collected,
                    "before_objects": before_objects,
                    "after_objects": after_objects,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Error in force GC: {e}")
                raise HTTPException(status_code=500, detail="خطا در garbage collection")
        
        @self.app.get("/health/status/detailed")
        async def detailed_status():
            """وضعیت تفصیلی سیستم"""
            try:
                # System info
                system_info = {
                    "cpu_percent": psutil.cpu_percent(interval=1),
                    "memory": dict(psutil.virtual_memory()._asdict()),
                    "swap": dict(psutil.swap_memory()._asdict()),
                    "disk": dict(psutil.disk_usage('/')._asdict()),
                    "boot_time": datetime.fromtimestamp(psutil.boot_time()).isoformat()
                }
                
                # Process info
                process = psutil.Process()
                process_info = {
                    "pid": process.pid,
                    "name": process.name(),
                    "status": process.status(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat(),
                    "cpu_percent": process.cpu_percent(),
                    "memory_info": dict(process.memory_info()._asdict()),
                    "num_threads": process.num_threads(),
                    "num_fds": process.num_fds() if hasattr(process, 'num_fds') else 0
                }
                
                # Monitor status
                monitor_status = self.monitor.get_status()
                
                return {
                    "system": system_info,
                    "process": process_info,
                    "monitor": monitor_status,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                self.logger.error(f"Error in detailed status: {e}")
                raise HTTPException(status_code=500, detail="خطا در وضعیت تفصیلی")
        
        @self.app.get("/health/config")
        async def get_config():
            """دریافت تنظیمات"""
            try:
                return {
                    "config": self.monitor.config,
                    "timestamp": datetime.now().isoformat()
                }
            except Exception as e:
                self.logger.error(f"Error getting config: {e}")
                raise HTTPException(status_code=500, detail="خطا در دریافت تنظیمات")

class MemoryHealthServer:
    """سرور Health Check"""
    
    def __init__(self, monitor: ProductionMemoryMonitor, host: str = "0.0.0.0", port: int = 8080):
        self.monitor = monitor
        self.host = host
        self.port = port
        self.api = MemoryHealthAPI(monitor)
        self.server = None
        self.logger = logging.getLogger(__name__)
    
    async def start_server(self):
        """راه‌اندازی سرور"""
        try:
            config = uvicorn.Config(
                app=self.api.app,
                host=self.host,
                port=self.port,
                log_level="info",
                access_log=True
            )
            self.server = uvicorn.Server(config)
            
            self.logger.info(f"🚀 Memory Health Check Server starting on http://{self.host}:{self.port}")
            await self.server.serve()
            
        except Exception as e:
            self.logger.error(f"Error starting health server: {e}")
            raise
    
    async def stop_server(self):
        """توقف سرور"""
        if self.server:
            self.server.should_exit = True
            self.logger.info("❌ Memory Health Check Server stopped")

async def main():
    """تست health endpoint"""
    from monitoring.production_memory_monitor import ProductionMemoryMonitor
    
    # Create monitor
    monitor = ProductionMemoryMonitor()
    
    # Create health server
    health_server = MemoryHealthServer(monitor, port=8080)
    
    try:
        # Start monitor
        await monitor.start_monitoring()
        
        # Start health server
        await health_server.start_server()
        
    except KeyboardInterrupt:
        print("\n⏹️ Stopping services...")
    finally:
        await monitor.stop_monitoring()
        await health_server.stop_server()
        print("✅ Services stopped.")

if __name__ == "__main__":
    asyncio.run(main()) 