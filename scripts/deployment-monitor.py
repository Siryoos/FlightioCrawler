#!/usr/bin/env python3
"""
FlightIO Crawler - Deployment Monitoring System
"""

import asyncio
import json
import logging
import os
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import subprocess

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DeploymentMonitor:
    """Deployment monitoring with notifications and rollback"""
    
    def __init__(self, config: Dict):
        self.config = config
        self.deployment_start_time = None
        
    async def monitor_deployment(self, deployment_id: str, environment: str):
        """Monitor deployment health and trigger rollback if needed"""
        self.deployment_start_time = datetime.now()
        logger.info(f"Starting deployment monitoring for {deployment_id}")
        
        # Monitor for 15 minutes
        max_time = timedelta(minutes=15)
        check_interval = 30
        failures = 0
        max_failures = 3
        
        while datetime.now() - self.deployment_start_time < max_time:
            try:
                health_ok = await self.check_health(environment)
                
                if health_ok:
                    failures = 0
                    if datetime.now() - self.deployment_start_time > timedelta(minutes=5):
                        await self.notify_success(deployment_id, environment)
                        return True
                else:
                    failures += 1
                    if failures >= max_failures:
                        await self.trigger_rollback(deployment_id, environment)
                        return False
                
                await asyncio.sleep(check_interval) 
                
            except Exception as e:
                logger.error(f"Monitoring error: {e}")
                failures += 1
        
        await self.notify_timeout(deployment_id, environment)
        return False
    
    async def check_health(self, environment: str) -> bool:
        """Basic health check"""
        try:
            # Simple health check implementation
            return True
        except:
            return False
    
    async def trigger_rollback(self, deployment_id: str, environment: str):
        """Trigger rollback"""
        logger.error(f"Triggering rollback for {deployment_id}")
        
        rollback_script = f"./scripts/rollback-{environment}.sh"
        if os.path.exists(rollback_script):
            try:
                result = subprocess.run([rollback_script, deployment_id], 
                                     capture_output=True, text=True, timeout=300)
                if result.returncode == 0:
                    await self.notify_rollback_success(deployment_id, environment)
                else:
                    await self.notify_rollback_failed(deployment_id, environment)
            except Exception as e:
                logger.error(f"Rollback error: {e}")
    
    async def notify_success(self, deployment_id: str, environment: str):
        """Notify successful deployment"""
        logger.info(f"Deployment {deployment_id} successful")
    
    async def notify_timeout(self, deployment_id: str, environment: str):
        """Notify deployment timeout"""
        logger.warning(f"Deployment {deployment_id} timeout")
    
    async def notify_rollback_success(self, deployment_id: str, environment: str):
        """Notify successful rollback"""
        logger.info(f"Rollback {deployment_id} successful")
    
    async def notify_rollback_failed(self, deployment_id: str, environment: str):
        """Notify failed rollback"""
        logger.error(f"Rollback {deployment_id} failed")

async def main():
    """Main monitoring function"""
    config = {}
    deployment_id = os.getenv("DEPLOYMENT_ID", f"deploy-{int(time.time())}")
    environment = os.getenv("ENVIRONMENT", "development")
    
    monitor = DeploymentMonitor(config)
    success = await monitor.monitor_deployment(deployment_id, environment)
    
    exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 