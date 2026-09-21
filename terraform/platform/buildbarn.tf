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

  # The Helm provider does not see edits inside a local chart directory; this digest, passed as a value, makes any change to
  # the chart (templates, values, config files) an upgrade.
  chart_dir    = "${path.module}/../../charts/buckroot-buildbarn"
  chart_digest = sha256(join("", [for f in sort(fileset(local.chart_dir, "**")) : filesha256("${local.chart_dir}/${f}")]))
}

resource "helm_release" "buildbarn" {
  name      = "buildbarn"
  namespace = kubernetes_namespace_v1.buildbarn.metadata[0].name
  chart     = local.chart_dir

  timeout = 900
  atomic  = true

  values = [yamlencode({
    chartDigest = local.chart_digest
    images      = { runner = var.runner_image }
    storage     = { casSizeGiB = var.cas_size_gib }
    keda = {
      enabled           = local.scaling_enabled
      prometheusAddress = "http://prometheus-server.${kubernetes_namespace_v1.monitoring.metadata[0].name}.svc.cluster.local:80"
    }
    pools = {
      for pool in ["shared", "dedicated", "legacy"] : pool => merge(
        contains(keys(var.worker_scaling_queries), pool) ? { scaling = { query = var.worker_scaling_queries[pool] } } : {},
        contains(keys(var.worker_replicas), pool) ? { worker = { replicas = var.worker_replicas[pool] } } : {},
      )
    }
  })]

  depends_on = [helm_release.keda, helm_release.prometheus]
}
