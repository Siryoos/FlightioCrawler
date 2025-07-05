#!/usr/bin/env python3
"""
FlightioCrawler Dependency Testing Script
This script verifies that all required dependencies are properly installed and configured.
"""

import sys
import os
import subprocess
import importlib
from typing import List, Dict, Tuple, Optional
import logging
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class DependencyTester:
    """Test all dependencies required for FlightioCrawler"""
    
    def __init__(self):
        self.test_results = []
        self.passed = 0
        self.failed = 0
        
    def test_python_version(self) -> bool:
        """Test Python version compatibility"""
        logger.info("🐍 Testing Python version...")
        
        version = sys.version_info
        if version.major == 3 and version.minor >= 8:
            logger.info(f"✅ Python version: {version.major}.{version.minor}.{version.micro}")
            return True
        else:
            logger.error(f"❌ Python version {version.major}.{version.minor}.{version.micro} not supported. Requires Python 3.8+")
            return False
    
    def test_python_packages(self) -> bool:
        """Test required Python packages"""
        logger.info("📦 Testing Python packages...")
        
        required_packages = [
            'aiohttp', 'asyncio', 'ssl', 'requests', 'urllib3', 'certifi',
            'beautifulsoup4', 'lxml', 'selenium', 'playwright', 'crawl4ai',
            'psycopg2', 'redis', 'fastapi', 'uvicorn', 'sqlalchemy',
            'celery', 'prometheus_client', 'hazm', 'pandas', 'numpy',
            'scikit-learn', 'websockets', 'pydantic', 'python-dotenv',
            'cryptography', 'bleach', 'validators', 'jdatetime'
        ]
        
        missing_packages = []
        for package in required_packages:
            try:
                # Handle package name variations
                if package == 'beautifulsoup4':
                    importlib.import_module('bs4')
                elif package == 'python-dotenv':
                    importlib.import_module('dotenv')
                elif package == 'scikit-learn':
                    importlib.import_module('sklearn')
                elif package == 'pillow':
                    importlib.import_module('PIL')
                else:
                    importlib.import_module(package)
                logger.info(f"✅ {package}")
            except ImportError:
                logger.error(f"❌ {package} not found")
                missing_packages.append(package)
        
        if missing_packages:
            logger.error(f"Missing packages: {', '.join(missing_packages)}")
            logger.info("Run: pip install -r requirements.txt")
            return False
        
        return True
    
    def test_system_commands(self) -> bool:
        """Test system commands availability"""
        logger.info("💻 Testing system commands...")
        
        commands = [
            'python3', 'pip3', 'git', 'curl', 'wget'
        ]
        
        missing_commands = []
        for cmd in commands:
            try:
                subprocess.run([cmd, '--version'], 
                             stdout=subprocess.DEVNULL, 
                             stderr=subprocess.DEVNULL, 
                             check=True)
                logger.info(f"✅ {cmd}")
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.error(f"❌ {cmd} not found")
                missing_commands.append(cmd)
        
        if missing_commands:
            logger.error(f"Missing commands: {', '.join(missing_commands)}")
            return False
        
        return True
    
    def test_browsers(self) -> bool:
        """Test browser availability"""
        logger.info("🌐 Testing browsers...")
        
        browsers = [
            ('chromium-browser', 'chromium-browser --version'),
            ('google-chrome', 'google-chrome --version'),
            ('chrome', 'chrome --version')
        ]
        
        browser_found = False
        for name, cmd in browsers:
            try:
                result = subprocess.run(cmd.split(), 
                                      capture_output=True, 
                                      text=True, 
                                      check=True)
                logger.info(f"✅ {name}: {result.stdout.strip()}")
                browser_found = True
                break
            except (subprocess.CalledProcessError, FileNotFoundError):
                logger.warning(f"⚠️ {name} not found")
        
        if not browser_found:
            logger.error("❌ No browser found. Install chromium-browser or google-chrome")
            return False
        
        return True
    
    def test_playwright_browsers(self) -> bool:
        """Test Playwright browser installation"""
        logger.info("🎭 Testing Playwright browsers...")
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                # Test Chromium
                try:
                    browser = p.chromium.launch()
                    browser.close()
                    logger.info("✅ Playwright Chromium")
                    return True
                except Exception as e:
                    logger.error(f"❌ Playwright Chromium: {e}")
                    logger.info("Run: playwright install chromium")
                    return False
                    
        except ImportError:
            logger.error("❌ Playwright not installed")
            return False
    
    def test_database_connection(self) -> bool:
        """Test database connection"""
        logger.info("🐘 Testing database connection...")
        
        try:
            import psycopg2
            
            # Try to connect to default PostgreSQL
            conn_params = {
                'host': os.getenv('DB_HOST', 'localhost'),
                'port': os.getenv('DB_PORT', '5432'),
                'user': os.getenv('DB_USER', 'postgres'),
                'password': os.getenv('DB_PASSWORD', ''),
                'database': os.getenv('DB_NAME', 'postgres')
            }
            
            try:
                conn = psycopg2.connect(**conn_params)
                conn.close()
                logger.info("✅ PostgreSQL connection")
                return True
            except psycopg2.Error as e:
                logger.error(f"❌ PostgreSQL connection failed: {e}")
                logger.info("Make sure PostgreSQL is running and credentials are correct")
                return False
                
        except ImportError:
            logger.error("❌ psycopg2 not installed")
            return False
    
    def test_redis_connection(self) -> bool:
        """Test Redis connection"""
        logger.info("🔴 Testing Redis connection...")
        
        try:
            import redis
            
            r = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=int(os.getenv('REDIS_PORT', '6379')),
                db=int(os.getenv('REDIS_DB', '0')),
                password=os.getenv('REDIS_PASSWORD', None)
            )
            
            r.ping()
            logger.info("✅ Redis connection")
            return True
            
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            logger.info("Make sure Redis is running")
            return False
    
    def test_ssl_configuration(self) -> bool:
        """Test SSL configuration"""
        logger.info("🔒 Testing SSL configuration...")
        
        try:
            import ssl
            import requests
            
            # Test SSL context creation
            ssl_context = ssl.create_default_context()
            logger.info("✅ SSL context creation")
            
            # Test HTTPS request with SSL bypass
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
            
            # Test a simple HTTPS request
            response = requests.get('https://httpbin.org/get', 
                                  timeout=10, 
                                  verify=False)
            if response.status_code == 200:
                logger.info("✅ HTTPS request with SSL bypass")
                return True
            else:
                logger.error(f"❌ HTTPS request failed with status {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"❌ SSL configuration test failed: {e}")
            return False
    
    def test_environment_files(self) -> bool:
        """Test environment files"""
        logger.info("📁 Testing environment files...")
        
        env_files = [
            '.env.system',
            'config/development.env',
            'config/staging.env'
        ]
        
        found_files = []
        for env_file in env_files:
            if os.path.exists(env_file):
                logger.info(f"✅ {env_file}")
                found_files.append(env_file)
            else:
                logger.warning(f"⚠️ {env_file} not found")
        
        if not found_files:
            logger.error("❌ No environment files found")
            return False
        
        return True
    
    def test_directory_structure(self) -> bool:
        """Test required directory structure"""
        logger.info("📂 Testing directory structure...")
        
        required_dirs = [
            'logs', 'screenshots', 'temp', 'data/cache',
            'config', 'adapters', 'api', 'tests'
        ]
        
        missing_dirs = []
        for dir_path in required_dirs:
            if not os.path.exists(dir_path):
                missing_dirs.append(dir_path)
                logger.warning(f"⚠️ {dir_path} not found")
            else:
                logger.info(f"✅ {dir_path}")
        
        if missing_dirs:
            logger.info(f"Creating missing directories: {', '.join(missing_dirs)}")
            for dir_path in missing_dirs:
                os.makedirs(dir_path, exist_ok=True)
        
        return True
    
    def test_persian_text_processing(self) -> bool:
        """Test Persian text processing"""
        logger.info("🔤 Testing Persian text processing...")
        
        try:
            import hazm
            
            # Test normalizer
            normalizer = hazm.Normalizer()
            test_text = "تست متن فارسی"
            normalized = normalizer.normalize(test_text)
            logger.info(f"✅ Persian text normalization: {normalized}")
            
            # Test word tokenizer
            tokenizer = hazm.WordTokenizer()
            tokens = tokenizer.tokenize(test_text)
            logger.info(f"✅ Persian tokenization: {tokens}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Persian text processing test failed: {e}")
            return False
    
    def run_all_tests(self) -> bool:
        """Run all dependency tests"""
        logger.info("🚀 Starting comprehensive dependency testing...")
        
        tests = [
            ("Python Version", self.test_python_version),
            ("Python Packages", self.test_python_packages),
            ("System Commands", self.test_system_commands),
            ("Browsers", self.test_browsers),
            ("Playwright Browsers", self.test_playwright_browsers),
            ("Database Connection", self.test_database_connection),
            ("Redis Connection", self.test_redis_connection),
            ("SSL Configuration", self.test_ssl_configuration),
            ("Environment Files", self.test_environment_files),
            ("Directory Structure", self.test_directory_structure),
            ("Persian Text Processing", self.test_persian_text_processing)
        ]
        
        for test_name, test_func in tests:
            logger.info(f"\n{'='*50}")
            logger.info(f"Testing: {test_name}")
            logger.info(f"{'='*50}")
            
            try:
                if test_func():
                    self.passed += 1
                    logger.info(f"✅ {test_name}: PASSED")
                else:
                    self.failed += 1
                    logger.error(f"❌ {test_name}: FAILED")
            except Exception as e:
                self.failed += 1
                logger.error(f"❌ {test_name}: ERROR - {e}")
        
        # Summary
        total = self.passed + self.failed
        logger.info(f"\n{'='*50}")
        logger.info(f"TEST SUMMARY")
        logger.info(f"{'='*50}")
        logger.info(f"Total Tests: {total}")
        logger.info(f"Passed: {self.passed}")
        logger.info(f"Failed: {self.failed}")
        logger.info(f"Success Rate: {(self.passed/total)*100:.1f}%")
        
        if self.failed == 0:
            logger.info("🎉 All tests passed! FlightioCrawler is ready to run.")
            return True
        else:
            logger.error("❌ Some tests failed. Please fix the issues above.")
            return False

def main():
    """Main function"""
    tester = DependencyTester()
    success = tester.run_all_tests()
    
    if not success:
        sys.exit(1)

if __name__ == "__main__":
    main() 