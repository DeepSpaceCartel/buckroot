# Buildbarn: remote cache and remote execution, the chart in ../../charts/buckroot-buildbarn.
#
# The namespace needs the "privileged" Pod Security level: the worker's runner container is privileged (every action starts
# a mount namespace). The exemption applies to this one namespace only, the same pattern as a BuildKit deployment needs.

resource "kubernetes_namespace_v1" "buildbarn" {
  metadata {
    name = "buildbarn"
    labels = {
      "pod-security.kubernetes.io/enforce" = "privileged"
    }
  }
}

locals {
  scaling_enabled = length(var.worker_scaling_queries) > 0
}

resource "helm_release" "buildbarn" {
  name      = "buildbarn"
  namespace = kubernetes_namespace_v1.buildbarn.metadata[0].name
  chart     = "${path.module}/../../charts/buckroot-buildbarn"

  timeout = 900
  atomic  = true

  values = [yamlencode({
    images  = { runner = var.runner_image }
    storage = { casSizeGiB = var.cas_size_gib }
    keda = {
      enabled           = local.scaling_enabled
      prometheusAddress = "http://prometheus-server.${kubernetes_namespace_v1.monitoring.metadata[0].name}.svc.cluster.local:80"
    }
    pools = {
      for pool, query in var.worker_scaling_queries : pool => { scaling = { query = query } }
    }
  })]

  depends_on = [helm_release.keda, helm_release.prometheus]
}
