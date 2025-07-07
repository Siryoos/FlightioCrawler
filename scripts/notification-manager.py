#!/usr/bin/env python3
"""
FlightIO Crawler - Notification Manager
"""

import asyncio
import json
import logging
import os
import smtplib
from datetime import datetime
from email.mime.text import MimeText
from typing import Dict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class NotificationManager:
    """Manage deployment notifications"""
    
    def __init__(self):
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.email_config = {
            "enabled": os.getenv("SMTP_ENABLED", "false").lower() == "true",
            "host": os.getenv("SMTP_HOST", "localhost"),
            "port": int(os.getenv("SMTP_PORT", "587")),
            "username": os.getenv("SMTP_USERNAME", ""),
            "password": os.getenv("SMTP_PASSWORD", ""),
            "from_email": os.getenv("SMTP_FROM", "noreply@flightio.com"),
            "to_email": os.getenv("ALERT_EMAIL", "admin@flightio.com")
        }
    
    async def send_notification(self, notification_type: str, data: Dict):
        """Send deployment notifications"""
        
        messages = {
            "deployment_started": "🚀 Deployment {deployment_id} started in {environment}",
            "deployment_success": "✅ Deployment {deployment_id} completed successfully",
            "deployment_failed": "❌ Deployment {deployment_id} failed in {environment}",
            "rollback_started": "🔄 Rollback initiated for deployment {deployment_id}",
            "rollback_success": "✅ Rollback completed successfully",
            "rollback_failed": "💥 Rollback failed for deployment {deployment_id}"
        }
        
        message = messages.get(notification_type, "📢 Deployment notification")
        formatted_message = message.format(**data)
        
        logger.info(f"Sending notification: {notification_type}")
        
        # Send to configured channels
        if self.slack_webhook:
            await self.send_slack(formatted_message, data)
        
        if self.email_config["enabled"]:
            await self.send_email(notification_type, formatted_message, data)
    
    async def send_slack(self, message: str, data: Dict):
        """Send Slack notification"""
        try:
            import aiohttp
            
            payload = {
                "text": message,
                "attachments": [{
                    "color": "good",
                    "fields": [
                        {"title": "Environment", "value": data.get("environment", "Unknown"), "short": True},
                        {"title": "Deployment ID", "value": data.get("deployment_id", "Unknown"), "short": True}
                    ]
                }]
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.slack_webhook, json=payload) as response:
                    if response.status == 200:
                        logger.info("Slack notification sent")
                    else:
                        logger.error(f"Slack notification failed: {response.status}")
                        
        except Exception as e:
            logger.error(f"Slack notification error: {e}")
    
    async def send_email(self, notification_type: str, message: str, data: Dict):
        """Send email notification"""
        try:
            msg = MimeText(f"{message}\n\nDetails: {json.dumps(data, indent=2)}")
            msg['Subject'] = f"FlightIO: {notification_type.replace('_', ' ').title()}"
            msg['From'] = self.email_config["from_email"]
            msg['To'] = self.email_config["to_email"]
            
            server = smtplib.SMTP(self.email_config["host"], self.email_config["port"])
            server.starttls()
            server.login(self.email_config["username"], self.email_config["password"])
            server.send_message(msg)
            server.quit()
            
            logger.info("Email notification sent")
            
        except Exception as e:
            logger.error(f"Email notification error: {e}")

async def main():
    """Test notifications"""
    manager = NotificationManager()
    
    test_data = {
        "deployment_id": "test-123",
        "environment": "staging"
    }
    
    await manager.send_notification("deployment_success", test_data)

if __name__ == "__main__":
    asyncio.run(main()) 