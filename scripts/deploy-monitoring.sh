#!/bin/bash

# Create namespace for monitoring
kubectl create namespace monitoring

# Apply Grafana secrets
kubectl apply -f k8s/grafana-secrets.yaml -n monitoring

# Apply Grafana provisioning
kubectl apply -f k8s/grafana-provisioning.yaml -n monitoring

# Apply Grafana dashboards
kubectl apply -f k8s/grafana-dashboards.yaml -n monitoring

# Apply Grafana datasources
kubectl apply -f k8s/grafana-datasources.yaml -n monitoring

# Apply monitoring stack
kubectl apply -f k8s/monitoring.yaml -n monitoring

# Wait for pods to be ready
echo "Waiting for pods to be ready..."
kubectl wait --for=condition=ready pod -l app=prometheus -n monitoring --timeout=300s
kubectl wait --for=condition=ready pod -l app=alertmanager -n monitoring --timeout=300s
kubectl wait --for=condition=ready pod -l app=grafana -n monitoring --timeout=300s

# Get Grafana service URL
echo "Grafana service URL:"
kubectl get svc grafana -n monitoring -o jsonpath='{.status.loadBalancer.ingress[0].ip}'
echo ":3000"

echo "Monitoring stack deployed successfully!" 