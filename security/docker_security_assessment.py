#!/usr/bin/env python3
"""
Docker Security Assessment Script for FlightIO Crawler
Comprehensive security vulnerability assessment and recommendations
"""

import os
import json
import yaml
import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

class SecurityLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class SecurityIssue:
    title: str
    description: str
    severity: SecurityLevel
    affected_files: List[str]
    recommendations: List[str]
    cwe_id: Optional[str] = None
    cvss_score: Optional[float] = None

class DockerSecurityAssessment:
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.issues: List[SecurityIssue] = []
        self.docker_files = self._find_docker_files()
        self.compose_files = self._find_compose_files()
        
    def _find_docker_files(self) -> List[Path]:
        """Find all Dockerfile variants in the project"""
        docker_files = []
        for pattern in ["Dockerfile*", "*.dockerfile"]:
            docker_files.extend(self.project_root.glob(pattern))
        return docker_files
    
    def _find_compose_files(self) -> List[Path]:
        """Find all docker-compose files in the project"""
        compose_files = []
        for pattern in ["docker-compose*.yml", "docker-compose*.yaml"]:
            compose_files.extend(self.project_root.glob(pattern))
        return compose_files
    
    def run_assessment(self) -> Dict:
        """Run complete security assessment"""
        print("🔍 Starting Docker Security Assessment...")
        
        # Check Dockerfile security
        self._check_dockerfile_security()
        
        # Check Docker Compose security
        self._check_compose_security()
        
        # Check container runtime security
        self._check_container_runtime_security()
        
        # Check secrets management
        self._check_secrets_management()
        
        # Check network security
        self._check_network_security()
        
        # Check image security
        self._check_image_security()
        
        return self._generate_report()
    
    def _check_dockerfile_security(self):
        """Check Dockerfile security best practices"""
        print("📋 Checking Dockerfile security...")
        
        for dockerfile in self.docker_files:
            content = dockerfile.read_text()
            
            # Check for root user
            if not re.search(r'USER\s+(?!root)', content):
                self.issues.append(SecurityIssue(
                    title="Container running as root",
                    description=f"Dockerfile {dockerfile.name} may run containers as root user",
                    severity=SecurityLevel.HIGH,
                    affected_files=[str(dockerfile)],
                    recommendations=[
                        "Create a non-root user and use USER directive",
                        "Use specific UID/GID numbers",
                        "Avoid running privileged containers"
                    ],
                    cwe_id="CWE-250"
                ))
            
            # Check for hardcoded secrets
            secret_patterns = [
                r'(password|passwd|pwd)\s*=\s*["\']?[^"\'\s]+',
                r'(api_key|apikey|secret|token)\s*=\s*["\']?[^"\'\s]+',
                r'(username|user)\s*=\s*["\']?[^"\'\s]+'
            ]
            
            for pattern in secret_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    self.issues.append(SecurityIssue(
                        title="Hardcoded secrets in Dockerfile",
                        description=f"Potential hardcoded secrets found in {dockerfile.name}",
                        severity=SecurityLevel.CRITICAL,
                        affected_files=[str(dockerfile)],
                        recommendations=[
                            "Use Docker secrets or environment variables",
                            "Use build-time secrets with BuildKit",
                            "Never embed secrets in container images"
                        ],
                        cwe_id="CWE-798"
                    ))
            
            # Check for latest tag usage
            if re.search(r'FROM\s+[^:\s]+:latest', content):
                self.issues.append(SecurityIssue(
                    title="Using 'latest' tag for base images",
                    description=f"Dockerfile {dockerfile.name} uses 'latest' tag which is not reproducible",
                    severity=SecurityLevel.MEDIUM,
                    affected_files=[str(dockerfile)],
                    recommendations=[
                        "Use specific version tags",
                        "Pin exact SHA256 digests",
                        "Use security-focused base images"
                    ],
                    cwe_id="CWE-1104"
                ))
    
    def _check_compose_security(self):
        """Check Docker Compose security configuration"""
        print("🐳 Checking Docker Compose security...")
        
        for compose_file in self.compose_files:
            try:
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
                
                services = compose_data.get('services', {})
                
                for service_name, service_config in services.items():
                    # Check for privileged containers
                    if service_config.get('privileged', False):
                        self.issues.append(SecurityIssue(
                            title="Privileged container",
                            description=f"Service {service_name} runs in privileged mode",
                            severity=SecurityLevel.HIGH,
                            affected_files=[str(compose_file)],
                            recommendations=[
                                "Remove privileged: true unless absolutely necessary",
                                "Use specific capabilities instead",
                                "Implement proper security contexts"
                            ],
                            cwe_id="CWE-250"
                        ))
                    
                    # Check for exposed ports
                    ports = service_config.get('ports', [])
                    for port in ports:
                        if isinstance(port, str) and not port.startswith('127.0.0.1:'):
                            self.issues.append(SecurityIssue(
                                title="Exposed ports without IP binding",
                                description=f"Service {service_name} exposes ports without IP binding",
                                severity=SecurityLevel.MEDIUM,
                                affected_files=[str(compose_file)],
                                recommendations=[
                                    "Bind ports to 127.0.0.1 for local access only",
                                    "Use reverse proxy for external access",
                                    "Implement proper firewall rules"
                                ],
                                cwe_id="CWE-200"
                            ))
                    
                    # Check for missing security options
                    security_opt = service_config.get('security_opt', [])
                    if 'no-new-privileges:true' not in security_opt:
                        self.issues.append(SecurityIssue(
                            title="Missing security options",
                            description=f"Service {service_name} missing security hardening options",
                            severity=SecurityLevel.MEDIUM,
                            affected_files=[str(compose_file)],
                            recommendations=[
                                "Add 'no-new-privileges:true' to security_opt",
                                "Configure appropriate AppArmor/SELinux profiles",
                                "Use read-only root filesystem where possible"
                            ],
                            cwe_id="CWE-250"
                        ))
                
            except Exception as e:
                self.issues.append(SecurityIssue(
                    title="Invalid Docker Compose file",
                    description=f"Error parsing {compose_file}: {str(e)}",
                    severity=SecurityLevel.MEDIUM,
                    affected_files=[str(compose_file)],
                    recommendations=[
                        "Validate YAML syntax",
                        "Check Docker Compose version compatibility",
                        "Review file permissions"
                    ]
                ))
    
    def _check_container_runtime_security(self):
        """Check container runtime security"""
        print("🏃 Checking container runtime security...")
        
        # Check if Docker daemon is running
        try:
            result = subprocess.run(['docker', 'info'], 
                                 capture_output=True, text=True, timeout=10)
            if result.returncode != 0:
                self.issues.append(SecurityIssue(
                    title="Docker daemon not accessible",
                    description="Cannot access Docker daemon for security checks",
                    severity=SecurityLevel.MEDIUM,
                    affected_files=[],
                    recommendations=[
                        "Ensure Docker daemon is running",
                        "Check Docker socket permissions",
                        "Verify user permissions"
                    ]
                ))
                return
        except subprocess.TimeoutExpired:
            self.issues.append(SecurityIssue(
                title="Docker daemon timeout",
                description="Docker daemon not responding",
                severity=SecurityLevel.MEDIUM,
                affected_files=[],
                recommendations=[
                    "Check Docker daemon status",
                    "Restart Docker service if needed",
                    "Check system resources"
                ]
            ))
            return
        except FileNotFoundError:
            self.issues.append(SecurityIssue(
                title="Docker not installed",
                description="Docker CLI not found",
                severity=SecurityLevel.HIGH,
                affected_files=[],
                recommendations=[
                    "Install Docker",
                    "Add Docker to system PATH",
                    "Verify installation"
                ]
            ))
            return
    
    def _check_secrets_management(self):
        """Check secrets management security"""
        print("🔐 Checking secrets management...")
        
        secrets_dir = self.project_root / "secrets"
        if not secrets_dir.exists():
            self.issues.append(SecurityIssue(
                title="Missing secrets directory",
                description="No secrets directory found for Docker secrets",
                severity=SecurityLevel.MEDIUM,
                affected_files=[],
                recommendations=[
                    "Create secrets directory",
                    "Generate secure secrets",
                    "Set proper file permissions (600)"
                ]
            ))
        else:
            # Check secrets file permissions
            for secret_file in secrets_dir.glob("*.txt"):
                try:
                    permissions = oct(secret_file.stat().st_mode)[-3:]
                    if permissions != '600':
                        self.issues.append(SecurityIssue(
                            title="Insecure secrets file permissions",
                            description=f"Secret file {secret_file.name} has permissions {permissions}",
                            severity=SecurityLevel.HIGH,
                            affected_files=[str(secret_file)],
                            recommendations=[
                                "Set file permissions to 600",
                                "Ensure only owner can read/write",
                                "Review file ownership"
                            ],
                            cwe_id="CWE-276"
                        ))
                except OSError:
                    pass
    
    def _check_network_security(self):
        """Check network security configuration"""
        print("🌐 Checking network security...")
        
        for compose_file in self.compose_files:
            try:
                with open(compose_file, 'r') as f:
                    compose_data = yaml.safe_load(f)
                
                networks = compose_data.get('networks', {})
                
                # Check for default network usage
                if not networks:
                    self.issues.append(SecurityIssue(
                        title="Using default Docker network",
                        description=f"Compose file {compose_file.name} uses default network",
                        severity=SecurityLevel.MEDIUM,
                        affected_files=[str(compose_file)],
                        recommendations=[
                            "Create custom networks",
                            "Use network segmentation",
                            "Implement network policies"
                        ],
                        cwe_id="CWE-200"
                    ))
                
                # Check for external networks
                for network_name, network_config in networks.items():
                    if isinstance(network_config, dict) and network_config.get('external', False):
                        self.issues.append(SecurityIssue(
                            title="External network usage",
                            description=f"Network {network_name} is external and may pose security risks",
                            severity=SecurityLevel.LOW,
                            affected_files=[str(compose_file)],
                            recommendations=[
                                "Review external network security",
                                "Implement network access controls",
                                "Monitor network traffic"
                            ]
                        ))
                
            except Exception:
                pass
    
    def _check_image_security(self):
        """Check container image security"""
        print("🖼️ Checking container image security...")
        
        # Check for base image vulnerabilities (if tools are available)
        common_vulnerable_images = [
            "ubuntu:latest",
            "debian:latest",
            "centos:latest",
            "alpine:latest"
        ]
        
        for dockerfile in self.docker_files:
            content = dockerfile.read_text()
            for vulnerable_image in common_vulnerable_images:
                if f"FROM {vulnerable_image}" in content:
                    self.issues.append(SecurityIssue(
                        title="Potentially vulnerable base image",
                        description=f"Using {vulnerable_image} which may have known vulnerabilities",
                        severity=SecurityLevel.MEDIUM,
                        affected_files=[str(dockerfile)],
                        recommendations=[
                            "Use security-focused base images",
                            "Scan images for vulnerabilities",
                            "Keep base images updated",
                            "Use distroless images when possible"
                        ],
                        cwe_id="CWE-1104"
                    ))
    
    def _generate_report(self) -> Dict:
        """Generate comprehensive security report"""
        print("📊 Generating security report...")
        
        # Count issues by severity
        severity_counts = {
            SecurityLevel.CRITICAL: 0,
            SecurityLevel.HIGH: 0,
            SecurityLevel.MEDIUM: 0,
            SecurityLevel.LOW: 0
        }
        
        for issue in self.issues:
            severity_counts[issue.severity] += 1
        
        # Calculate risk score
        risk_score = (
            severity_counts[SecurityLevel.CRITICAL] * 10 +
            severity_counts[SecurityLevel.HIGH] * 5 +
            severity_counts[SecurityLevel.MEDIUM] * 2 +
            severity_counts[SecurityLevel.LOW] * 1
        )
        
        report = {
            "timestamp": str(subprocess.run(['date'], capture_output=True, text=True).stdout.strip()),
            "assessment_summary": {
                "total_issues": len(self.issues),
                "critical_issues": severity_counts[SecurityLevel.CRITICAL],
                "high_issues": severity_counts[SecurityLevel.HIGH],
                "medium_issues": severity_counts[SecurityLevel.MEDIUM],
                "low_issues": severity_counts[SecurityLevel.LOW],
                "risk_score": risk_score,
                "risk_level": self._get_risk_level(risk_score)
            },
            "files_analyzed": {
                "dockerfiles": [str(f) for f in self.docker_files],
                "compose_files": [str(f) for f in self.compose_files]
            },
            "security_issues": [
                {
                    "title": issue.title,
                    "description": issue.description,
                    "severity": issue.severity.value,
                    "affected_files": issue.affected_files,
                    "recommendations": issue.recommendations,
                    "cwe_id": issue.cwe_id,
                    "cvss_score": issue.cvss_score
                }
                for issue in self.issues
            ],
            "recommendations": self._get_general_recommendations()
        }
        
        return report
    
    def _get_risk_level(self, score: int) -> str:
        """Get risk level based on score"""
        if score >= 30:
            return "CRITICAL"
        elif score >= 20:
            return "HIGH"
        elif score >= 10:
            return "MEDIUM"
        else:
            return "LOW"
    
    def _get_general_recommendations(self) -> List[str]:
        """Get general security recommendations"""
        return [
            "Implement regular security scanning in CI/CD pipeline",
            "Use Docker Bench for Security for additional checks",
            "Enable Docker Content Trust for image signing",
            "Implement proper log monitoring and alerting",
            "Regular security updates and patch management",
            "Use least privilege principle for all containers",
            "Implement network segmentation and firewalls",
            "Regular backup and disaster recovery testing",
            "Security training for development team",
            "Implement security as code practices"
        ]
    
    def save_report(self, filename: str = "docker_security_report.json"):
        """Save security report to file"""
        report = self._generate_report()
        
        with open(filename, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"📄 Security report saved to {filename}")
        return report

def main():
    """Main function to run security assessment"""
    print("🔒 FlightIO Docker Security Assessment Tool")
    print("=" * 50)
    
    assessment = DockerSecurityAssessment()
    report = assessment.run_assessment()
    
    # Print summary
    print("\n📋 SECURITY ASSESSMENT SUMMARY")
    print("=" * 50)
    print(f"Total Issues Found: {report['assessment_summary']['total_issues']}")
    print(f"Critical: {report['assessment_summary']['critical_issues']}")
    print(f"High: {report['assessment_summary']['high_issues']}")
    print(f"Medium: {report['assessment_summary']['medium_issues']}")
    print(f"Low: {report['assessment_summary']['low_issues']}")
    print(f"Risk Level: {report['assessment_summary']['risk_level']}")
    
    # Save report
    assessment.save_report()
    
    # Print top issues
    if report['security_issues']:
        print("\n🚨 TOP SECURITY ISSUES")
        print("=" * 50)
        for issue in sorted(report['security_issues'], 
                          key=lambda x: ['low', 'medium', 'high', 'critical'].index(x['severity']),
                          reverse=True)[:5]:
            print(f"• {issue['title']} ({issue['severity'].upper()})")
            print(f"  {issue['description']}")
            print()

if __name__ == "__main__":
    main() 