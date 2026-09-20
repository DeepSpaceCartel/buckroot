# A small Prometheus: it scrapes every pod annotated prometheus.io/scrape=true (all Buildbarn components are) and is the
# metric source of the KEDA scalers. Nothing here is for people; Grafana and dashboards are a later addition.

resource "kubernetes_namespace_v1" "monitoring" {
  metadata {
    name = "monitoring"
  }
}

resource "helm_release" "prometheus" {
  name      = "prometheus"
  namespace = kubernetes_namespace_v1.monitoring.metadata[0].name

  repository = "https://prometheus-community.github.io/helm-charts"
  chart      = "prometheus"
  version    = var.prometheus_chart_version

  timeout = 900
  atomic  = true

  values = [yamlencode({
    alertmanager           = { enabled = false }
    prometheus-pushgateway = { enabled = false }
    server = {
      retention        = "48h"
      persistentVolume = { size = "10Gi" }
      # It runs on the always-on platform node; a worker node can be gone at any time.
      nodeSelector = { "buckroot.dev/pool" = "platform" }
    }
  })]
}
