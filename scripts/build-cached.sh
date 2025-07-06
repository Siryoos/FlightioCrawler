#!/bin/bash

# Build script with caching enabled
# This script builds all services with Docker BuildKit caching

set -e

echo "🚀 Starting Docker build with caching..."

# Enable Docker BuildKit
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Build with caching
echo "📦 Building with cache..."
docker-compose --profile production build --parallel --build-arg BUILDKIT_INLINE_CACHE=1

echo "✅ Build completed successfully!"
echo "🎯 You can now run: docker-compose --profile production up" 