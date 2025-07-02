# FlightIO Optimized Build Script - PowerShell Version
# Implements parallel builds, advanced caching, and build performance optimizations

param(
    [string]$Registry = "ghcr.io/flightio",
    [string]$Tag = "latest",
    [string]$BuildContext = ".",
    [int]$ParallelBuilds = 4,
    [string]$Platform = "linux/amd64,linux/arm64",
    [switch]$NoCache,
    [switch]$Cleanup,
    [switch]$Help
)

# Build targets configuration
$Targets = @(
    @{Service="api"; Dockerfile="Dockerfile.api"},
    @{Service="crawler"; Dockerfile="Dockerfile.crawler"},
    @{Service="monitor"; Dockerfile="Dockerfile.monitor"},
    @{Service="worker"; Dockerfile="Dockerfile.worker"},
    @{Service="frontend"; Dockerfile="frontend/Dockerfile"}
)

Write-Host "🚀 Starting FlightIO Optimized Build Process..." -ForegroundColor Blue

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

# Function to show help
function Show-Help {
    Write-Host "FlightIO Optimized Build Script" -ForegroundColor Green
    Write-Host "Usage: .\build-optimized.ps1 [OPTIONS]" -ForegroundColor White
    Write-Host ""
    Write-Host "Options:" -ForegroundColor Yellow
    Write-Host "  -Registry REGISTRY     Container registry (default: $Registry)"
    Write-Host "  -Tag TAG              Image tag (default: $Tag)"
    Write-Host "  -ParallelBuilds COUNT Parallel builds (default: $ParallelBuilds)"
    Write-Host "  -Platform PLATFORM    Target platforms (default: $Platform)"
    Write-Host "  -NoCache              Disable build cache"
    Write-Host "  -Cleanup              Clean build cache and exit"
    Write-Host "  -Help                 Show this help"
}

# Function to setup BuildKit
function Setup-BuildKit {
    Write-Info "Setting up Docker BuildKit..."
    
    $env:DOCKER_BUILDKIT = "1"
    $env:BUILDX_EXPERIMENTAL = "1"
    
    # Check if buildx instance exists
    $builderExists = docker buildx inspect flightio-builder 2>$null
    if (-not $builderExists) {
        Write-Info "Creating new buildx instance..."
        docker buildx create --name flightio-builder --use `
            --driver docker-container `
            --driver-opt network=host
    } else {
        docker buildx use flightio-builder
    }
    
    # Bootstrap the builder
    docker buildx inspect --bootstrap
    
    Write-Success "BuildKit setup completed"
}

# Function to get build metadata
function Get-BuildMetadata($service) {
    $gitVersion = try { git describe --tags --always 2>$null } catch { "dev" }
    $gitRevision = try { git rev-parse HEAD 2>$null } catch { "unknown" }
    $created = Get-Date -Format "yyyy-MM-ddTHH:mm:ssZ" -AsUTC
    
    return @(
        "org.opencontainers.image.title=FlightIO-$service",
        "org.opencontainers.image.description=FlightIO $service service",
        "org.opencontainers.image.version=$gitVersion",
        "org.opencontainers.image.revision=$gitRevision",
        "org.opencontainers.image.created=$created"
    )
}

# Function to build a single service
function Build-Service($target) {
    $service = $target.Service
    $dockerfile = $target.Dockerfile
    $contextDir = $BuildContext
    
    # Adjust context for frontend
    if ($service -eq "frontend") {
        $contextDir = "frontend"
    }
    
    Write-Info "Building $service service..."
    
    # Prepare build metadata
    $metadata = Get-BuildMetadata $service
    $labels = $metadata | ForEach-Object { "--label", $_ }
    
    # Prepare cache arguments
    $cacheArgs = @()
    if (-not $NoCache) {
        $cacheArgs += "--cache-from", "type=gha"
        $cacheArgs += "--cache-to", "type=gha,mode=max"
    }
    
    # Build arguments
    $buildArgs = @(
        "buildx", "build",
        "--file", $dockerfile,
        "--context", $contextDir,
        "--tag", "$Registry/$service`:$Tag",
        "--tag", "$Registry/$service`:latest",
        "--platform", $Platform,
        "--build-arg", "BUILDKIT_INLINE_CACHE=1",
        "--build-arg", "BUILDX_EXPERIMENTAL=1"
    ) + $cacheArgs + $labels + @("--push", ".")
    
    # Start build process
    $buildStart = Get-Date
    $process = Start-Process -FilePath "docker" -ArgumentList $buildArgs -NoNewWindow -PassThru -RedirectStandardOutput "build-$service.log" -RedirectStandardError "build-$service-error.log"
    
    return @{
        Service = $service
        Process = $process
        StartTime = $buildStart
    }
}

# Function to wait for builds completion
function Wait-ForBuilds($buildJobs) {
    Write-Info "Waiting for all builds to complete..."
    $failedBuilds = @()
    $completedBuilds = @()
    
    foreach ($job in $buildJobs) {
        $job.Process.WaitForExit()
        $endTime = Get-Date
        $duration = $endTime - $job.StartTime
        
        if ($job.Process.ExitCode -eq 0) {
            Write-Success "$($job.Service) build completed successfully in $($duration.TotalSeconds)s"
            $completedBuilds += $job.Service
        } else {
            Write-Error "$($job.Service) build failed"
            $failedBuilds += $job.Service
        }
    }
    
    if ($failedBuilds.Count -gt 0) {
        Write-Error "Failed builds: $($failedBuilds -join ', ')"
        return $false
    }
    
    Write-Success "All builds completed successfully!"
    return $true
}

# Function to analyze build performance
function Analyze-BuildPerformance {
    Write-Info "Analyzing build performance..."
    
    Write-Host "`n📊 Build Performance Report:" -ForegroundColor Blue
    Write-Host "==============================="
    
    foreach ($target in $Targets) {
        $service = $target.Service
        $logFile = "build-$service.log"
        
        if (Test-Path $logFile) {
            $imageSize = try {
                (docker images --format "{{.Size}}" "$Registry/$service`:$Tag" 2>$null) -replace "`n", ""
            } catch { "N/A" }
            
            Write-Host "$service`:" -ForegroundColor Green
            Write-Host "  Image Size: $imageSize"
            Write-Host "  Log File: $logFile"
            Write-Host ""
        }
    }
}

# Function to cleanup build cache
function Cleanup-BuildCache {
    Write-Info "Cleaning up build cache..."
    try {
        docker builder prune -f --filter until=168h 2>$null
        docker system prune -f --filter until=24h 2>$null
        Write-Success "Build cache cleanup completed"
    } catch {
        Write-Warning "Build cache cleanup failed: $_"
    }
}

# Function to prebuild base images
function Prebuild-BaseImages {
    Write-Info "Pre-building base images for better caching..."
    
    $baseDockerfile = @"
FROM python:3.11-slim as base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --upgrade pip setuptools wheel
"@
    
    $baseDockerfile | Out-File -FilePath "Dockerfile.base" -Encoding UTF8
    
    try {
        $cacheArgs = if (-not $NoCache) { @("--cache-from", "type=gha", "--cache-to", "type=gha,mode=max") } else { @() }
        
        docker buildx build --file Dockerfile.base --tag "$Registry/base:$Tag" --platform $Platform @cacheArgs --push . 2>$null
        Write-Success "Base image pre-building completed"
    } catch {
        Write-Warning "Base image build failed, continuing..."
    } finally {
        Remove-Item "Dockerfile.base" -ErrorAction SilentlyContinue
    }
}

# Main execution
function Main {
    if ($Help) {
        Show-Help
        return
    }
    
    if ($Cleanup) {
        Cleanup-BuildCache
        return
    }
    
    $startTime = Get-Date
    
    Write-Info "Build configuration:"
    Write-Info "  Registry: $Registry"
    Write-Info "  Tag: $Tag"
    Write-Info "  Parallel builds: $ParallelBuilds"
    Write-Info "  Platform: $Platform"
    Write-Info "  Cache enabled: $(-not $NoCache)"
    
    # Setup BuildKit
    Setup-BuildKit
    
    # Pre-build base images
    Prebuild-BaseImages
    
    # Start parallel builds
    $buildJobs = @()
    $activeBuildCount = 0
    
    foreach ($target in $Targets) {
        # Wait if we've reached parallel build limit
        while ($activeBuildCount -ge $ParallelBuilds) {
            Start-Sleep -Seconds 1
            $activeBuildCount = ($buildJobs | Where-Object { -not $_.Process.HasExited }).Count
        }
        
        $job = Build-Service $target
        $buildJobs += $job
        $activeBuildCount++
        
        Write-Info "Started build $($buildJobs.Count)/$($Targets.Count) for $($target.Service)"
    }
    
    # Wait for all builds to complete
    $success = Wait-ForBuilds $buildJobs
    
    # Analyze performance
    Analyze-BuildPerformance
    
    # Calculate total time
    $endTime = Get-Date
    $totalTime = ($endTime - $startTime).TotalSeconds
    
    if ($success) {
        Write-Success "🎉 All builds completed in ${totalTime}s!"
    } else {
        Write-Error "Some builds failed. Check the logs for details."
        exit 1
    }
    
    # Cleanup logs
    Write-Info "Cleaning up build logs..."
    Remove-Item "build-*.log", "build-*-error.log" -ErrorAction SilentlyContinue
}

# Execute main function
Main 