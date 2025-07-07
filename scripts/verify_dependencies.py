#!/usr/bin/env python3
"""
Dependency Verification Script for FlightIO Crawler
Verifies all required dependencies are properly installed and working
"""

import sys
import os
import subprocess
import importlib
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Color codes for output
class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'
    END = '\033[0m'

def print_header(text: str):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text.center(60)}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*60}{Colors.END}")

def print_success(text: str):
    """Print success message"""
    print(f"{Colors.GREEN}✓ {text}{Colors.END}")

def print_error(text: str):
    """Print error message"""
    print(f"{Colors.RED}✗ {text}{Colors.END}")

def print_warning(text: str):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠ {text}{Colors.END}")

def print_info(text: str):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ {text}{Colors.END}")

class DependencyVerifier:
    """Comprehensive dependency verification system"""
    
    def __init__(self):
        self.results = {
            'python_version': None,
            'system_commands': {},
            'python_packages': {},
            'playwright_browsers': {},
            'ssl_verification': None,
            'overall_status': 'unknown'
        }
        self.errors = []
        self.warnings = []
        
    def verify_python_version(self) -> bool:
        """Verify Python version"""
        print_header("Python Version Check")
        
        try:
            version = sys.version_info
            version_str = f"{version.major}.{version.minor}.{version.micro}"
            
            if version.major >= 3 and version.minor >= 8:
                self.results['python_version'] = {
                    'version': version_str,
                    'status': 'success',
                    'path': sys.executable
                }
                print_success(f"Python {version_str} - Compatible")
                print_info(f"Python path: {sys.executable}")
                return True
            else:
                self.results['python_version'] = {
                    'version': version_str,
                    'status': 'error',
                    'error': 'Python 3.8+ required'
                }
                print_error(f"Python {version_str} - Requires Python 3.8+")
                self.errors.append("Python version too old")
                return False
                
        except Exception as e:
            self.results['python_version'] = {
                'status': 'error',
                'error': str(e)
            }
            print_error(f"Failed to check Python version: {e}")
            self.errors.append(f"Python version check failed: {e}")
            return False
    
    def verify_system_commands(self) -> bool:
        """Verify system commands availability"""
        print_header("System Commands Check")
        
        commands = {
            'git': 'Version control system',
            'curl': 'HTTP client for downloads',
            'wget': 'HTTP client for downloads (alternative)',
            'psql': 'PostgreSQL client (optional)',
            'redis-cli': 'Redis client (optional)',
            'chromium': 'Chromium browser (alternative)',
            'chromium-browser': 'Chromium browser (alternative)',
            'google-chrome': 'Google Chrome browser (alternative)'
        }
        
        all_success = True
        
        for cmd, description in commands.items():
            try:
                result = subprocess.run([cmd, '--version'], 
                                      capture_output=True, 
                                      text=True, 
                                      timeout=10)
                
                if result.returncode == 0:
                    version_line = result.stdout.split('\n')[0]
                    self.results['system_commands'][cmd] = {
                        'status': 'success',
                        'version': version_line.strip(),
                        'description': description
                    }
                    print_success(f"{cmd}: {version_line.strip()}")
                else:
                    self.results['system_commands'][cmd] = {
                        'status': 'error',
                        'error': 'Command failed',
                        'description': description
                    }
                    if cmd in ['git', 'curl']:  # Essential commands
                        print_error(f"{cmd}: Not available (required)")
                        self.errors.append(f"Missing required command: {cmd}")
                        all_success = False
                    else:
                        print_warning(f"{cmd}: Not available (optional)")
                        self.warnings.append(f"Missing optional command: {cmd}")
                        
            except subprocess.TimeoutExpired:
                self.results['system_commands'][cmd] = {
                    'status': 'error',
                    'error': 'Command timeout',
                    'description': description
                }
                print_warning(f"{cmd}: Timeout")
                
            except FileNotFoundError:
                self.results['system_commands'][cmd] = {
                    'status': 'not_found',
                    'error': 'Command not found',
                    'description': description
                }
                if cmd in ['git', 'curl']:  # Essential commands
                    print_error(f"{cmd}: Not found (required)")
                    self.errors.append(f"Missing required command: {cmd}")
                    all_success = False
                else:
                    print_warning(f"{cmd}: Not found (optional)")
                    
            except Exception as e:
                self.results['system_commands'][cmd] = {
                    'status': 'error',
                    'error': str(e),
                    'description': description
                }
                print_error(f"{cmd}: Error - {e}")
        
        return all_success
    
    def verify_python_packages(self) -> bool:
        """Verify Python packages"""
        print_header("Python Packages Check")
        
        required_packages = {
            'aiohttp': 'HTTP client for async requests',
            'beautifulsoup4': 'HTML parsing',
            'selenium': 'Browser automation',
            'playwright': 'Modern browser automation',
            'asyncpg': 'PostgreSQL async driver',
            'redis': 'Redis client',
            'certifi': 'SSL certificate bundle',
            'urllib3': 'HTTP client library',
            'psutil': 'System monitoring',
            'lxml': 'XML/HTML processing',
            'requests': 'HTTP client library'
        }
        
        optional_packages = {
            'fastapi': 'Web framework',
            'uvicorn': 'ASGI server',
            'pydantic': 'Data validation',
            'python-dotenv': 'Environment variable loading'
        }
        
        all_success = True
        
        # Check required packages
        for package, description in required_packages.items():
            try:
                module = importlib.import_module(package)
                version = getattr(module, '__version__', 'unknown')
                
                self.results['python_packages'][package] = {
                    'status': 'success',
                    'version': version,
                    'description': description,
                    'required': True
                }
                print_success(f"{package}: {version}")
                
            except ImportError as e:
                self.results['python_packages'][package] = {
                    'status': 'error',
                    'error': str(e),
                    'description': description,
                    'required': True
                }
                print_error(f"{package}: Not available (required)")
                self.errors.append(f"Missing required package: {package}")
                all_success = False
                
            except Exception as e:
                self.results['python_packages'][package] = {
                    'status': 'error',
                    'error': str(e),
                    'description': description,
                    'required': True
                }
                print_error(f"{package}: Error - {e}")
                all_success = False
        
        # Check optional packages
        for package, description in optional_packages.items():
            try:
                module = importlib.import_module(package)
                version = getattr(module, '__version__', 'unknown')
                
                self.results['python_packages'][package] = {
                    'status': 'success',
                    'version': version,
                    'description': description,
                    'required': False
                }
                print_success(f"{package}: {version} (optional)")
                
            except ImportError:
                self.results['python_packages'][package] = {
                    'status': 'not_found',
                    'error': 'Package not found',
                    'description': description,
                    'required': False
                }
                print_warning(f"{package}: Not available (optional)")
                self.warnings.append(f"Missing optional package: {package}")
                
        return all_success
    
    def verify_playwright_browsers(self) -> bool:
        """Verify Playwright browser installations"""
        print_header("Playwright Browsers Check")
        
        try:
            from playwright.sync_api import sync_playwright
            
            with sync_playwright() as p:
                browsers = {
                    'chromium': p.chromium,
                    'firefox': p.firefox,
                    'webkit': p.webkit
                }
                
                all_success = True
                
                for browser_name, browser in browsers.items():
                    try:
                        # Try to get browser executable path
                        browser_instance = browser.launch(headless=True)
                        version = browser_instance.version
                        browser_instance.close()
                        
                        self.results['playwright_browsers'][browser_name] = {
                            'status': 'success',
                            'version': version
                        }
                        
                        if browser_name == 'chromium':
                            print_success(f"{browser_name}: {version} (required)")
                        else:
                            print_success(f"{browser_name}: {version} (optional)")
                            
                    except Exception as e:
                        self.results['playwright_browsers'][browser_name] = {
                            'status': 'error',
                            'error': str(e)
                        }
                        
                        if browser_name == 'chromium':
                            print_error(f"{browser_name}: Not available (required) - {e}")
                            self.errors.append(f"Chromium browser not available: {e}")
                            all_success = False
                        else:
                            print_warning(f"{browser_name}: Not available (optional) - {e}")
                            self.warnings.append(f"{browser_name} browser not available")
                
                return all_success
                
        except ImportError:
            self.results['playwright_browsers'] = {
                'status': 'error',
                'error': 'Playwright not installed'
            }
            print_error("Playwright not installed")
            self.errors.append("Playwright not installed")
            return False
            
        except Exception as e:
            self.results['playwright_browsers'] = {
                'status': 'error',
                'error': str(e)
            }
            print_error(f"Playwright check failed: {e}")
            self.errors.append(f"Playwright check failed: {e}")
            return False
    
    def verify_ssl_functionality(self) -> bool:
        """Verify SSL functionality"""
        print_header("SSL Functionality Check")
        
        try:
            # Test basic SSL import
            import ssl
            import certifi
            
            # Test SSL context creation
            context = ssl.create_default_context()
            ca_bundle = certifi.where()
            
            self.results['ssl_verification'] = {
                'status': 'success',
                'ssl_version': ssl.OPENSSL_VERSION,
                'certifi_bundle': ca_bundle,
                'default_context': 'created successfully'
            }
            
            print_success(f"SSL Version: {ssl.OPENSSL_VERSION}")
            print_success(f"Certifi bundle: {ca_bundle}")
            print_success("SSL context creation: OK")
            
            # Test SSL manager if available
            try:
                sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                from security.ssl_manager import get_ssl_manager
                
                ssl_manager = get_ssl_manager()
                stats = ssl_manager.get_ssl_statistics()
                
                print_success(f"SSL Manager: {stats['config']['mode']}")
                self.results['ssl_verification']['ssl_manager'] = stats['config']
                
            except ImportError:
                print_warning("SSL Manager not available (custom implementation)")
            except Exception as e:
                print_warning(f"SSL Manager check failed: {e}")
            
            return True
            
        except Exception as e:
            self.results['ssl_verification'] = {
                'status': 'error',
                'error': str(e)
            }
            print_error(f"SSL verification failed: {e}")
            self.errors.append(f"SSL verification failed: {e}")
            return False
    
    def generate_summary(self) -> Dict[str, Any]:
        """Generate verification summary"""
        print_header("Verification Summary")
        
        # Count results
        total_checks = 0
        passed_checks = 0
        
        # Python version
        total_checks += 1
        if self.results['python_version'] and self.results['python_version']['status'] == 'success':
            passed_checks += 1
        
        # System commands (count only required ones)
        required_commands = ['git', 'curl']
        for cmd in required_commands:
            total_checks += 1
            if (cmd in self.results['system_commands'] and 
                self.results['system_commands'][cmd]['status'] == 'success'):
                passed_checks += 1
        
        # Python packages (count only required ones)
        for package, info in self.results['python_packages'].items():
            if info.get('required', False):
                total_checks += 1
                if info['status'] == 'success':
                    passed_checks += 1
        
        # Playwright browsers (only chromium is required)
        total_checks += 1
        if ('chromium' in self.results['playwright_browsers'] and 
            self.results['playwright_browsers']['chromium']['status'] == 'success'):
            passed_checks += 1
        
        # SSL functionality
        total_checks += 1
        if (self.results['ssl_verification'] and 
            self.results['ssl_verification']['status'] == 'success'):
            passed_checks += 1
        
        success_rate = (passed_checks / total_checks) * 100 if total_checks > 0 else 0
        
        # Determine overall status
        if success_rate >= 90:
            self.results['overall_status'] = 'excellent'
            status_color = Colors.GREEN
            status_text = "EXCELLENT"
        elif success_rate >= 80:
            self.results['overall_status'] = 'good'
            status_color = Colors.GREEN
            status_text = "GOOD"
        elif success_rate >= 70:
            self.results['overall_status'] = 'fair'
            status_color = Colors.YELLOW
            status_text = "FAIR"
        else:
            self.results['overall_status'] = 'poor'
            status_color = Colors.RED
            status_text = "POOR"
        
        # Print summary
        print(f"\n{Colors.BOLD}Overall Status: {status_color}{status_text}{Colors.END}")
        print(f"{Colors.BOLD}Success Rate: {status_color}{success_rate:.1f}%{Colors.END}")
        print(f"{Colors.BOLD}Checks Passed: {passed_checks}/{total_checks}{Colors.END}")
        
        if self.errors:
            print(f"\n{Colors.RED}{Colors.BOLD}Errors ({len(self.errors)}):{Colors.END}")
            for error in self.errors:
                print(f"  {Colors.RED}• {error}{Colors.END}")
        
        if self.warnings:
            print(f"\n{Colors.YELLOW}{Colors.BOLD}Warnings ({len(self.warnings)}):{Colors.END}")
            for warning in self.warnings:
                print(f"  {Colors.YELLOW}• {warning}{Colors.END}")
        
        # Recommendations
        print(f"\n{Colors.BOLD}{Colors.BLUE}Recommendations:{Colors.END}")
        
        if self.results['overall_status'] == 'excellent':
            print(f"{Colors.GREEN}• All dependencies are properly installed!{Colors.END}")
            print(f"{Colors.GREEN}• FlightIO Crawler is ready to run{Colors.END}")
        elif self.results['overall_status'] == 'good':
            print(f"{Colors.GREEN}• Core dependencies are installed{Colors.END}")
            print(f"{Colors.YELLOW}• Consider installing optional dependencies for full functionality{Colors.END}")
        else:
            print(f"{Colors.RED}• Install missing required dependencies before running FlightIO Crawler{Colors.END}")
            print(f"{Colors.YELLOW}• Run: ./scripts/install_dependencies.sh{Colors.END}")
            print(f"{Colors.YELLOW}• Or install manually: pip3 install -r requirements.txt{Colors.END}")
        
        return {
            'total_checks': total_checks,
            'passed_checks': passed_checks,
            'success_rate': success_rate,
            'overall_status': self.results['overall_status'],
            'errors': self.errors,
            'warnings': self.warnings
        }
    
    def save_report(self, filename: str = None):
        """Save verification report to file"""
        if filename is None:
            filename = f"dependency_verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        import json
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'results': self.results,
            'errors': self.errors,
            'warnings': self.warnings
        }
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        print_info(f"Detailed report saved to: {filename}")
        return filename
    
    def run_full_verification(self) -> bool:
        """Run complete dependency verification"""
        print_header("FlightIO Crawler Dependency Verification")
        print_info(f"Verification started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run all verification steps
        steps = [
            self.verify_python_version,
            self.verify_system_commands,
            self.verify_python_packages,
            self.verify_playwright_browsers,
            self.verify_ssl_functionality
        ]
        
        all_passed = True
        for step in steps:
            try:
                if not step():
                    all_passed = False
            except Exception as e:
                print_error(f"Verification step failed: {e}")
                self.errors.append(f"Verification step failed: {e}")
                all_passed = False
        
        # Generate summary
        summary = self.generate_summary()
        
        # Save report
        self.save_report()
        
        return summary['overall_status'] in ['excellent', 'good']


def main():
    """Main function"""
    verifier = DependencyVerifier()
    
    try:
        success = verifier.run_full_verification()
        return 0 if success else 1
    except KeyboardInterrupt:
        print_error("\nVerification interrupted by user")
        return 1
    except Exception as e:
        print_error(f"Verification failed: {e}")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code) 