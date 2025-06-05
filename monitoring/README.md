# Monitoring Stack

This directory contains configuration files for Prometheus, Grafana and Alertmanager.

## Running on Kubernetes

1. Create the monitoring namespace:
   ```bash
   kubectl apply -f k8s/namespace.yaml
   ```
2. Deploy Prometheus, Grafana and exporters:
   ```bash
   kubectl apply -f k8s/prometheus.yaml
   kubectl apply -f k8s/grafana.yaml
   kubectl apply -f k8s/node-exporter.yaml
   kubectl apply -f k8s/postgres-exporter.yaml
   kubectl apply -f k8s/redis-exporter.yaml
   kubectl apply -f k8s/kube-state-metrics.yaml
   ```
3. Apply alerting rules and Alertmanager:
   ```bash
   kubectl apply -f k8s/alertmanager.yaml
   kubectl apply -f k8s/monitoring.yaml
   ```
4. Access Grafana via the service `grafana` in the `monitoring` namespace. Default credentials are defined in `k8s/grafana-secrets.yaml`.
5. Import dashboards from `grafana_dashboards/` or use `grafana_dashboard.json` for a quick overview dashboard.

## Configuration Files

- `prometheus.yml` – Prometheus scrape configuration.
- `alertmanager.yml` – Alert routing to Slack or other receivers.
- `alert_rules.yml` – Collection of alerting rules for crawler components.
- `grafana_dashboard.json` – Example Grafana dashboard definition.
- `grafana_dashboards/` – Additional dashboards organised per component.


