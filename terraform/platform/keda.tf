# KEDA scales the Buildbarn worker Deployments on the scheduler's queue depth (see buildbarn.tf and the chart's keda.yaml).

resource "kubernetes_namespace_v1" "keda" {
  metadata {
    name = "keda"
  }
}

resource "helm_release" "keda" {
  name      = "keda"
  namespace = kubernetes_namespace_v1.keda.metadata[0].name

  repository = "https://kedacore.github.io/charts"
  chart      = "keda"
  version    = var.keda_chart_version

  timeout = 900
  atomic  = true
}
