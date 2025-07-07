#!/bin/bash
# Remove the monitoring stack from Kubernetes
set -e

echo "Deleting monitoring stack..."

kubectl delete -f k8s/monitoring.yaml -n monitoring --ignore-not-found
kubectl delete -f k8s/grafana-datasources.yaml -n monitoring --ignore-not-found
kubectl delete -f k8s/grafana-dashboards.yaml -n monitoring --ignore-not-found
kubectl delete -f k8s/grafana-provisioning.yaml -n monitoring --ignore-not-found
kubectl delete -f k8s/grafana-secrets.yaml -n monitoring --ignore-not-found

# Remove namespace last
kubectl delete namespace monitoring --ignore-not-found

echo "Monitoring stack removed."
