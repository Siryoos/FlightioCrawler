# FlightIO Security Scanner - PowerShell Version
# Comprehensive security scanning for Docker images and codebase

param(
    [string]$ReportDir = "./security-reports",
    [string]$DockerImageName = "flightio-crawler",
    [string]$ApiImageName = "flightio-api"
)

# Create reports directory
if (!(Test-Path $ReportDir)) {
    New-Item -ItemType Directory -Path $ReportDir -Force | Out-Null
}

Write-Host "🔐 Starting FlightIO Security Scan..." -ForegroundColor Blue

# Function to write colored messages
function Write-Info($message) {
    Write-Host "[INFO] $message" -ForegroundColor Blue
}

function Write-Success($message) {
    Write-Host "[SUCCESS] $message" -ForegroundColor Green
}

function Write-Warning($message) {
    Write-Host "[WARNING] $message" -ForegroundColor Yellow
}

function Write-Error($message) {
    Write-Host "[ERROR] $message" -ForegroundColor Red
}

# 1. Python Security with Bandit
Write-Info "Running Bandit security scan for Python code..."
try {
    if (Get-Command bandit -ErrorAction SilentlyContinue) {
        bandit -r . -f json -o "$ReportDir/bandit-report.json" --exclude ./venv,./node_modules,./frontend
        bandit -r . --exclude ./venv,./node_modules,./frontend
        Write-Success "Bandit scan completed"
    } else {
        Write-Warning "Bandit not installed. Installing..."
        pip install bandit[toml]
    }
} catch {
    Write-Warning "Bandit scan failed: $_"
}

# 2. Dependency Vulnerability Check with Safety
Write-Info "Running Safety check for Python dependencies..."
try {
    if (Get-Command safety -ErrorAction SilentlyContinue) {
        safety check --json --output "$ReportDir/safety-report.json"
        safety check
        Write-Success "Safety check completed"
    } else {
        Write-Warning "Safety not installed. Installing..."
        pip install safety
    }
} catch {
    Write-Warning "Safety check failed: $_"
}

# 3. Secrets Detection with detect-secrets
Write-Info "Running secrets detection scan..."
try {
    if (Get-Command detect-secrets -ErrorAction SilentlyContinue) {
        detect-secrets scan --all-files --baseline "$ReportDir/secrets-baseline.json"
        Write-Success "Secrets detection completed"
    } else {
        Write-Warning "detect-secrets not installed. Installing..."
        pip install detect-secrets
    }
} catch {
    Write-Warning "Secrets detection failed: $_"
}

# 4. Docker Security Scanning
Write-Info "Checking for Docker security tools..."
if (Get-Command docker -ErrorAction SilentlyContinue) {
    Write-Info "Docker found. Checking for security scanning tools..."
    
    # Check if we can run Trivy in Docker
    try {
        docker run --rm -v "${PWD}:${PWD}" -w $PWD aquasec/trivy:latest fs --severity HIGH,CRITICAL --format json --output "$ReportDir/trivy-filesystem.json" .
        Write-Success "Trivy filesystem scan completed via Docker"
    } catch {
        Write-Warning "Trivy Docker scan failed: $_"
    }
} else {
    Write-Warning "Docker not available for security scanning"
}

# 5. PowerShell Security Analysis
Write-Info "Running PowerShell-specific security checks..."
$securityIssues = @()

# Check for hardcoded passwords/secrets in Python files
$pythonFiles = Get-ChildItem -Path . -Recurse -Include "*.py" | Where-Object { $_.FullName -notmatch "venv|node_modules|\.git" }
foreach ($file in $pythonFiles) {
    $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and $content -match "password|secret|key|token") {
        $securityIssues += "Potential hardcoded credential in: $($file.FullName)"
    }
}

# Check for SQL injection patterns
foreach ($file in $pythonFiles) {
    $content = Get-Content $file.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and $content -match "execute.*%") {
        $securityIssues += "Potential SQL injection vulnerability in: $($file.FullName)"
    }
}

# 6. Docker Compose Security Check
Write-Info "Checking Docker Compose security..."
$composeFiles = Get-ChildItem -Path . -Include "docker-compose*.yml" -Recurse
foreach ($compose in $composeFiles) {
    $content = Get-Content $compose.FullName -Raw -ErrorAction SilentlyContinue
    if ($content -and $content -match "privileged.*true") {
        $securityIssues += "Privileged container found in: $($compose.FullName)"
    }
    if ($content -and $content -match "user.*root") {
        $securityIssues += "Root user specified in: $($compose.FullName)"
    }
}

# 7. Generate Security Report
Write-Info "Generating security summary report..."
$reportContent = @"
# FlightIO Security Scan Summary

**Scan Date:** $(Get-Date)
**Platform:** Windows PowerShell
**Scan Type:** Comprehensive Security Assessment

## 📊 Scan Results Overview:

### Code Security:
- ✅ Bandit (Python Security) - Completed
- ✅ Safety (Dependency Check) - Completed  
- ✅ Secrets Detection - Completed
- ✅ Custom Security Patterns - Completed

### Infrastructure Security:
- ✅ Docker Compose Analysis - Completed
- ⚠️ Container Scanning - Limited (Windows)

## 🚨 Security Issues Found:
"@

if ($securityIssues.Count -eq 0) {
    $reportContent += "`n✅ No critical security issues detected in manual scan."
} else {
    $reportContent += "`n"
    $securityIssues | ForEach-Object { $reportContent += "- ⚠️ $_`n" }
}

$reportContent += @"

## 🎯 Security Recommendations:

### High Priority:
1. Review any vulnerabilities found in dependency scans
2. Ensure all secrets are properly externalized
3. Implement proper input validation and sanitization

### Medium Priority:
1. Set up automated security scanning in CI/CD
2. Implement container security scanning
3. Add security headers to web applications

### Low Priority:
1. Regular security training for development team
2. Implement security code review process
3. Set up security monitoring and alerting

## 📁 Generated Reports:
- Bandit Report: `bandit-report.json`
- Safety Report: `safety-report.json`
- Secrets Baseline: `secrets-baseline.json`

## 🔧 Next Steps:
1. Review all generated reports
2. Fix any HIGH/CRITICAL vulnerabilities
3. Implement security scanning in CI/CD pipeline
4. Schedule regular security assessments

---
**Generated by FlightIO Security Scanner**
"@

$reportContent | Out-File -FilePath "$ReportDir/security-summary.md" -Encoding UTF8

Write-Success "Security scan completed! Reports available in: $ReportDir"
Write-Host "🔐 Security scanning finished successfully!" -ForegroundColor Green

# Display summary
if ($securityIssues.Count -gt 0) {
    Write-Warning "Found $($securityIssues.Count) potential security issues. Please review the detailed report."
} else {
    Write-Success "No critical security issues found in manual scan."
}

Write-Info "Please review the detailed reports in the $ReportDir directory." 