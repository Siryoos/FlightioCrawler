#!/usr/bin/env python3
"""
SSL Manager Test Script
Tests the SSL manager functionality and connectivity to target websites
"""

import asyncio
import logging
import sys
import os
import json
from datetime import datetime
from typing import Dict, List, Any

# Add parent directory to path to import modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from security.ssl_manager import SSLManager, SSLConfig, SSLMode
from config import PRODUCTION_SITES

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class SSLTester:
    """Comprehensive SSL testing system"""
    
    def __init__(self):
        self.test_results = {}
        self.start_time = datetime.now()
        
    async def run_comprehensive_tests(self) -> Dict[str, Any]:
        """Run comprehensive SSL tests"""
        logger.info("Starting comprehensive SSL tests...")
        
        # Test different SSL modes
        await self._test_ssl_modes()
        
        # Test target websites
        await self._test_target_websites()
        
        # Test SSL diagnostics
        await self._test_ssl_diagnostics()
        
        # Generate report
        report = self._generate_report()
        
        logger.info("SSL tests completed successfully")
        return report
    
    async def _test_ssl_modes(self):
        """Test different SSL modes"""
        logger.info("Testing different SSL modes...")
        
        modes = [SSLMode.BYPASS, SSLMode.PERMISSIVE, SSLMode.STRICT]
        test_url = "https://httpbin.org/get"
        
        for mode in modes:
            logger.info(f"Testing SSL mode: {mode.value}")
            
            try:
                # Create SSL manager with specific mode
                config = SSLConfig(mode=mode)
                ssl_manager = SSLManager(config)
                
                # Test connectivity
                result = await ssl_manager.verify_ssl_connection(test_url)
                
                self.test_results[f"ssl_mode_{mode.value}"] = {
                    "mode": mode.value,
                    "test_url": test_url,
                    "success": result.get("ssl_verified", False),
                    "error": result.get("error"),
                    "status_code": result.get("status_code"),
                    "certificate_info": result.get("certificate_info")
                }
                
                logger.info(f"SSL mode {mode.value}: {'SUCCESS' if result.get('ssl_verified') else 'FAILED'}")
                
            except Exception as e:
                self.test_results[f"ssl_mode_{mode.value}"] = {
                    "mode": mode.value,
                    "test_url": test_url,
                    "success": False,
                    "error": str(e)
                }
                logger.error(f"SSL mode {mode.value} failed: {e}")
    
    async def _test_target_websites(self):
        """Test connectivity to target websites"""
        logger.info("Testing target websites...")
        
        # Get target URLs from config
        target_sites = PRODUCTION_SITES if 'PRODUCTION_SITES' in globals() else {}
        
        # Default test sites if config not available
        if not target_sites:
            target_sites = {
                "flytoday": {"base_url": "https://www.flytoday.ir"},
                "alibaba": {"base_url": "https://www.alibaba.ir"},
                "safarmarket": {"base_url": "https://www.safarmarket.com"},
                "partocrs": {"base_url": "https://www.partocrs.com"},
                "partoticket": {"base_url": "https://www.partoticket.com"},
                "bookcharter724": {"base_url": "https://www.bookcharter724.ir"},
                "bookcharter": {"base_url": "https://www.bookcharter.ir"},
                "mz724": {"base_url": "https://www.mz724.com"},
                "pegasus": {"base_url": "https://www.flypgs.com"}
            }
        
        urls_to_test = []
        for site_name, site_config in target_sites.items():
            if "base_url" in site_config:
                urls_to_test.append(site_config["base_url"])
        
        # Test with different SSL modes
        for mode in [SSLMode.BYPASS, SSLMode.PERMISSIVE]:
            logger.info(f"Testing target websites with {mode.value} mode...")
            
            config = SSLConfig(mode=mode)
            ssl_manager = SSLManager(config)
            
            # Test all URLs
            results = await ssl_manager.test_ssl_connectivity(urls_to_test)
            
            self.test_results[f"target_websites_{mode.value}"] = {
                "mode": mode.value,
                "total_sites": len(urls_to_test),
                "results": results,
                "successful_sites": sum(1 for r in results.values() if r.get("ssl_verified", False)),
                "failed_sites": sum(1 for r in results.values() if not r.get("ssl_verified", False))
            }
            
            successful = sum(1 for r in results.values() if r.get("ssl_verified", False))
            logger.info(f"Target websites {mode.value}: {successful}/{len(urls_to_test)} successful")
    
    async def _test_ssl_diagnostics(self):
        """Test SSL diagnostics functionality"""
        logger.info("Testing SSL diagnostics...")
        
        try:
            # Create SSL manager
            ssl_manager = SSLManager()
            
            # Get statistics
            stats = ssl_manager.get_ssl_statistics()
            
            # Export diagnostics
            diagnostics_file = f"ssl_diagnostics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            ssl_manager.export_diagnostics(diagnostics_file)
            
            self.test_results["ssl_diagnostics"] = {
                "statistics": stats,
                "diagnostics_file": diagnostics_file,
                "success": True
            }
            
            logger.info("SSL diagnostics test: SUCCESS")
            
        except Exception as e:
            self.test_results["ssl_diagnostics"] = {
                "success": False,
                "error": str(e)
            }
            logger.error(f"SSL diagnostics test failed: {e}")
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive test report"""
        end_time = datetime.now()
        duration = (end_time - self.start_time).total_seconds()
        
        # Count overall results
        total_tests = len(self.test_results)
        successful_tests = sum(1 for result in self.test_results.values() 
                             if result.get("success", False))
        
        # Analyze target website results
        best_mode = None
        best_success_rate = 0
        
        for key, result in self.test_results.items():
            if key.startswith("target_websites_"):
                mode = result.get("mode", "unknown")
                success_rate = result.get("successful_sites", 0) / result.get("total_sites", 1)
                
                if success_rate > best_success_rate:
                    best_success_rate = success_rate
                    best_mode = mode
        
        # Generate summary
        report = {
            "test_summary": {
                "start_time": self.start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "duration_seconds": duration,
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "success_rate": successful_tests / total_tests if total_tests > 0 else 0,
                "best_ssl_mode": best_mode,
                "best_success_rate": best_success_rate
            },
            "detailed_results": self.test_results,
            "recommendations": self._generate_recommendations()
        }
        
        return report
    
    def _generate_recommendations(self) -> List[str]:
        """Generate recommendations based on test results"""
        recommendations = []
        
        # Check if any mode worked
        bypass_result = self.test_results.get("target_websites_bypass", {})
        permissive_result = self.test_results.get("target_websites_permissive", {})
        
        bypass_success = bypass_result.get("successful_sites", 0)
        permissive_success = permissive_result.get("successful_sites", 0)
        
        if bypass_success == 0 and permissive_success == 0:
            recommendations.append("CRITICAL: No SSL mode successfully connected to target websites")
            recommendations.append("Check network connectivity and DNS resolution")
            recommendations.append("Consider using SSL bypass mode for development")
        elif bypass_success > permissive_success:
            recommendations.append("SSL bypass mode shows better results")
            recommendations.append("Consider using bypass mode for development environment")
            recommendations.append("Investigate certificate issues for production deployment")
        elif permissive_success > bypass_success:
            recommendations.append("SSL permissive mode shows better results")
            recommendations.append("Consider using permissive mode for better security")
        
        if bypass_success > 0:
            recommendations.append("At least some sites are accessible with SSL bypass")
            recommendations.append("SSL issues are likely due to certificate verification problems")
        
        # Check SSL diagnostics
        diagnostics_result = self.test_results.get("ssl_diagnostics", {})
        if diagnostics_result.get("success"):
            recommendations.append("SSL diagnostics working correctly")
        else:
            recommendations.append("SSL diagnostics failed - check SSL manager configuration")
        
        return recommendations
    
    def save_report(self, report: Dict[str, Any], filename: str = None):
        """Save test report to file"""
        if filename is None:
            filename = f"ssl_test_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Test report saved to: {filename}")
        return filename


async def main():
    """Main function to run SSL tests"""
    try:
        tester = SSLTester()
        report = await tester.run_comprehensive_tests()
        
        # Save report
        filename = tester.save_report(report)
        
        # Print summary
        print("\n" + "="*60)
        print("SSL MANAGER TEST SUMMARY")
        print("="*60)
        
        summary = report["test_summary"]
        print(f"Duration: {summary['duration_seconds']:.2f} seconds")
        print(f"Total Tests: {summary['total_tests']}")
        print(f"Successful Tests: {summary['successful_tests']}")
        print(f"Success Rate: {summary['success_rate']:.2%}")
        print(f"Best SSL Mode: {summary['best_ssl_mode']}")
        print(f"Best Success Rate: {summary['best_success_rate']:.2%}")
        
        print("\nRecommendations:")
        for i, rec in enumerate(report["recommendations"], 1):
            print(f"{i}. {rec}")
        
        print(f"\nDetailed report saved to: {filename}")
        
        # Return appropriate exit code
        if summary['success_rate'] > 0.5:
            return 0
        else:
            return 1
            
    except Exception as e:
        logger.error(f"SSL test failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code) 