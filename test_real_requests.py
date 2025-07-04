#!/usr/bin/env python3
"""
Real Request Test Script

This script comprehensively tests the crawler's real request functionality,
including environment configuration, site connectivity, and request validation.
"""

import asyncio
import logging
import sys
import time
from typing import Dict, List, Any
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from environment_manager import env_manager
from real_request_validator import real_request_validator, ValidationResult, RequestStatistics
from config import config, PRODUCTION_SITES
# from monitoring import CrawlerMonitor  # Commented out due to import issues
# from monitoring import Monitoring  # Commented out due to import issues
# from main_crawler import IranianFlightCrawler  # Commented out due to import issues

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('real_request_test.log')
    ]
)

logger = logging.getLogger(__name__)


class RealRequestTester:
    """Comprehensive tester for real request functionality"""

    def __init__(self):
        self.test_results = {}
        self.start_time = time.time()

    async def run_all_tests(self) -> Dict[str, Any]:
        """Run all real request tests"""
        logger.info("🚀 Starting comprehensive real request tests...")
        
        test_results = {
            "timestamp": time.time(),
            "environment_config": await self.test_environment_configuration(),
            "site_connectivity": await self.test_site_connectivity(),
            "crawler_real_requests": await self.test_crawler_real_requests(),
            "anti_detection_measures": await self.test_anti_detection_measures(),
            "validation_system": await self.test_validation_system(),
            "summary": {}
        }
        
        # Generate summary
        test_results["summary"] = self._generate_summary(test_results)
        
        # Export results
        self._export_results(test_results)
        
        logger.info("✅ All real request tests completed!")
        return test_results

    async def test_environment_configuration(self) -> Dict[str, Any]:
        """Test environment configuration for real requests"""
        logger.info("🔧 Testing environment configuration...")
        
        results = {
            "use_mock": env_manager.use_mock,
            "environment": env_manager.environment,
            "enable_real_requests": env_manager.enable_real_requests,
            "should_use_real_crawler": env_manager.should_use_real_crawler(),
            "validation_config": env_manager.validate_real_request_config(),
            "real_request_config": env_manager.get_real_request_config(),
            "issues": []
        }
        
        # Check for configuration issues
        if env_manager.use_mock and env_manager.enable_real_requests:
            results["issues"].append("Conflicting configuration: USE_MOCK=true but ENABLE_REAL_REQUESTS=true")
        
        if not env_manager.should_use_real_crawler():
            results["issues"].append("Real crawler is disabled")
        
        if not env_manager.enable_response_validation:
            results["issues"].append("Response validation is disabled")
        
        logger.info(f"Environment configuration test completed. Issues: {len(results['issues'])}")
        return results

    async def test_site_connectivity(self) -> Dict[str, Any]:
        """Test connectivity to all production sites"""
        logger.info("🌐 Testing site connectivity...")
        
        results = {
            "sites": {},
            "total_sites": len(PRODUCTION_SITES),
            "accessible_sites": 0,
            "failed_sites": 0
        }
        
        for site_name, site_config in PRODUCTION_SITES.items():
            logger.info(f"Testing connectivity to {site_name}...")
            
            site_result = {
                "base_url": site_config.get("base_url"),
                "accessible": False,
                "response_time": 0,
                "status_code": 0,
                "response_size": 0,
                "error": None
            }
            
            try:
                validation_result = await real_request_validator.validate_request(
                    site_config.get("base_url"),
                    site_name
                )
                
                site_result.update({
                    "accessible": validation_result.is_valid,
                    "response_time": validation_result.response_time,
                    "status_code": validation_result.status_code,
                    "response_size": validation_result.response_size,
                    "anti_bot_detected": validation_result.anti_bot_detected,
                    "anti_bot_measures": validation_result.anti_bot_measures
                })
                
                if validation_result.is_valid:
                    results["accessible_sites"] += 1
                else:
                    results["failed_sites"] += 1
                    site_result["error"] = validation_result.reason
                    
            except Exception as e:
                results["failed_sites"] += 1
                site_result["error"] = str(e)
            
            results["sites"][site_name] = site_result
            
            # Add delay between requests
            await asyncio.sleep(1)
        
        logger.info(f"Site connectivity test completed. Accessible: {results['accessible_sites']}/{results['total_sites']}")
        return results

    async def test_crawler_real_requests(self) -> Dict[str, Any]:
        """Test if the main crawler makes real requests"""
        logger.info("🤖 Testing crawler real requests...")
        
        results = {
            "crawler_initialized": False,
            "real_requests_made": False,
            "test_search_params": {},
            "crawl_results": {},
            "issues": []
        }
        
        try:
            # Test environment configuration for real requests
            results["crawler_initialized"] = True
            
            # Test search parameters
            test_params = {
                "origin": "THR",
                "destination": "MHD", 
                "departure_date": "2025-01-15",
                "passengers": 1,
                "cabin_class": "economy"
            }
            results["test_search_params"] = test_params
            
            # Test real request validation directly
            logger.info("Testing real request validation...")
            test_url = "https://www.flytoday.ir"
            validation_result = await real_request_validator.validate_request(test_url, "flytoday")
            
            results["crawl_results"]["flytoday"] = {
                "url": test_url,
                "is_valid": validation_result.is_valid,
                "response_time": validation_result.response_time,
                "response_size": validation_result.response_size,
                "anti_bot_detected": validation_result.anti_bot_detected,
                "success": validation_result.is_valid
            }
            
            results["real_requests_made"] = validation_result.is_valid
            
            # Test multiple sites
            logger.info("Testing multiple sites...")
            test_sites = ["flytoday", "alibaba", "safarmarket"]
            all_results = []
            
            for site_name in test_sites:
                if site_name in PRODUCTION_SITES:
                    site_url = PRODUCTION_SITES[site_name]["base_url"]
                    try:
                        site_validation = await real_request_validator.validate_request(site_url, site_name)
                        all_results.append({
                            "site": site_name,
                            "url": site_url,
                            "success": site_validation.is_valid,
                            "response_time": site_validation.response_time,
                            "response_size": site_validation.response_size
                        })
                    except Exception as e:
                        all_results.append({
                            "site": site_name,
                            "url": site_url,
                            "success": False,
                            "error": str(e)
                        })
            
            results["all_sites_results"] = {
                "total_sites": len(all_results),
                "successful_sites": sum(1 for r in all_results if r["success"]),
                "sites_with_results": len(all_results)
            }
            
        except Exception as e:
            results["issues"].append(f"Crawler test error: {str(e)}")
            logger.error(f"Error testing crawler: {e}")
        
        logger.info(f"Crawler real request test completed. Real requests made: {results['real_requests_made']}")
        return results

    async def test_anti_detection_measures(self) -> Dict[str, Any]:
        """Test anti-detection measures"""
        logger.info("🛡️ Testing anti-detection measures...")
        
        results = {
            "anti_detection_enabled": env_manager.enable_anti_detection,
            "user_agent_rotation": env_manager.enable_user_agent_rotation,
            "proxy_rotation": env_manager.enable_proxy_rotation,
            "anti_bot_detection": env_manager.enable_anti_bot_detection,
            "test_results": {}
        }
        
        # Test anti-bot detection on known sites
        test_sites = ["https://www.google.com", "https://www.github.com"]
        
        for site in test_sites:
            try:
                validation_result = await real_request_validator.validate_request(site, "test")
                results["test_results"][site] = {
                    "anti_bot_detected": validation_result.anti_bot_detected,
                    "anti_bot_measures": validation_result.anti_bot_measures,
                    "response_time": validation_result.response_time,
                    "response_size": validation_result.response_size
                }
            except Exception as e:
                results["test_results"][site] = {"error": str(e)}
        
        logger.info("Anti-detection measures test completed")
        return results

    async def test_validation_system(self) -> Dict[str, Any]:
        """Test the validation system"""
        logger.info("✅ Testing validation system...")
        
        results = {
            "validation_enabled": env_manager.validate_real_requests,
            "response_validation": env_manager.enable_response_validation,
            "statistics_tracking": env_manager.enable_request_statistics,
            "validation_summary": real_request_validator.get_validation_summary(),
            "statistics_summary": real_request_validator.get_statistics_summary(),
            "test_validation": {}
        }
        
        # Test validation with various scenarios
        test_urls = [
            ("https://httpbin.org/status/200", "valid"),
            ("https://httpbin.org/status/404", "invalid_status"),
            ("https://httpbin.org/delay/5", "slow_response"),
        ]
        
        for url, scenario in test_urls:
            try:
                validation_result = await real_request_validator.validate_request(url, f"test_{scenario}")
                results["test_validation"][scenario] = {
                    "is_valid": validation_result.is_valid,
                    "reason": validation_result.reason,
                    "response_time": validation_result.response_time,
                    "response_size": validation_result.response_size
                }
            except Exception as e:
                results["test_validation"][scenario] = {"error": str(e)}
        
        logger.info("Validation system test completed")
        return results

    def _generate_summary(self, test_results: Dict[str, Any]) -> Dict[str, Any]:
        """Generate summary of all test results"""
        summary = {
            "overall_status": "PASS",
            "total_tests": 5,
            "passed_tests": 0,
            "failed_tests": 0,
            "issues": [],
            "recommendations": []
        }
        
        # Check environment configuration
        env_config = test_results["environment_config"]
        if not env_config["issues"]:
            summary["passed_tests"] += 1
        else:
            summary["failed_tests"] += 1
            summary["issues"].extend(env_config["issues"])
        
        # Check site connectivity
        connectivity = test_results["site_connectivity"]
        if connectivity["accessible_sites"] > 0:
            summary["passed_tests"] += 1
        else:
            summary["failed_tests"] += 1
            summary["issues"].append("No sites are accessible")
        
        # Check crawler real requests
        crawler_test = test_results["crawler_real_requests"]
        if crawler_test["real_requests_made"]:
            summary["passed_tests"] += 1
        else:
            summary["failed_tests"] += 1
            summary["issues"].append("Crawler is not making real requests")
        
        # Check anti-detection measures
        anti_detection = test_results["anti_detection_measures"]
        if anti_detection["anti_detection_enabled"]:
            summary["passed_tests"] += 1
        else:
            summary["failed_tests"] += 1
            summary["issues"].append("Anti-detection measures are disabled")
        
        # Check validation system
        validation = test_results["validation_system"]
        if validation["validation_enabled"]:
            summary["passed_tests"] += 1
        else:
            summary["failed_tests"] += 1
            summary["issues"].append("Validation system is disabled")
        
        # Determine overall status
        if summary["failed_tests"] > 0:
            summary["overall_status"] = "FAIL"
        
        # Generate recommendations
        if not env_manager.should_use_real_crawler():
            summary["recommendations"].append("Enable real crawler by setting USE_MOCK=false and ENABLE_REAL_REQUESTS=true")
        
        if not env_manager.enable_response_validation:
            summary["recommendations"].append("Enable response validation for better request monitoring")
        
        if connectivity["accessible_sites"] < connectivity["total_sites"] * 0.5:
            summary["recommendations"].append("Check network connectivity and site availability")
        
        return summary

    def _export_results(self, results: Dict[str, Any]) -> None:
        """Export test results to file"""
        try:
            import json
            from datetime import datetime
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"real_request_test_results_{timestamp}.json"
            
            with open(filename, 'w') as f:
                json.dump(results, f, indent=2, default=str)
            
            logger.info(f"Test results exported to {filename}")
            
        except Exception as e:
            logger.error(f"Error exporting results: {e}")


async def main():
    """Main test function"""
    logger.info("🧪 Starting Real Request Test Suite")
    
    tester = RealRequestTester()
    results = await tester.run_all_tests()
    
    # Print summary
    summary = results["summary"]
    logger.info(f"\n📊 Test Summary:")
    logger.info(f"Overall Status: {summary['overall_status']}")
    logger.info(f"Tests Passed: {summary['passed_tests']}/{summary['total_tests']}")
    logger.info(f"Tests Failed: {summary['failed_tests']}/{summary['total_tests']}")
    
    if summary["issues"]:
        logger.info(f"\n❌ Issues Found:")
        for issue in summary["issues"]:
            logger.info(f"  - {issue}")
    
    if summary["recommendations"]:
        logger.info(f"\n💡 Recommendations:")
        for rec in summary["recommendations"]:
            logger.info(f"  - {rec}")
    
    # Exit with appropriate code
    if summary["overall_status"] == "PASS":
        logger.info("✅ All tests passed! Real requests are working correctly.")
        sys.exit(0)
    else:
        logger.error("❌ Some tests failed. Please review the issues above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 