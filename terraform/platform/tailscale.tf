# Reach the cluster's web UIs from a desktop over Tailscale instead of a port-forward. The operator runs in the cluster, keeps a tailnet
# device per exposed Service or Ingress, and gets HTTPS certificates from Tailscale; nothing is exposed to the internet.
#
# Needs an OAuth client in the tailnet (Settings > OAuth clients: scopes Devices Core and Auth Keys, both write, tag
# tag:k8s-operator) and, in the policy file, tagOwners for tag:k8s-operator and tag:k8s. See docs/guides/kubernetes.md.

resource "kubernetes_namespace_v1" "tailscale" {
  metadata {
    name = "tailscale"
    # The operator's proxy pods need NET_ADMIN and a privileged init container to set up forwarding, which the default baseline
    # Pod Security level refuses. Only this namespace is relaxed.
    labels = { "pod-security.kubernetes.io/enforce" = "privileged" }
  }
}

resource "helm_release" "tailscale_operator" {
  name      = "tailscale-operator"
  namespace = kubernetes_namespace_v1.tailscale.metadata[0].name

  repository = "https://pkgs.tailscale.com/helmcharts"
  chart      = "tailscale-operator"
  version    = var.tailscale_chart_version

  timeout = 600
  atomic  = true

  values = [yamlencode({
    oauth          = { clientId = var.tailscale_client_id, clientSecret = var.tailscale_client_secret }
    operatorConfig = { hostname = "buckroot-k8s-operator" }
  })]
}

# Coder on the tailnet: https://<coder_tailnet_hostname>.<tailnet>.ts.net, TLS terminated by the Tailscale proxy.
resource "kubernetes_ingress_v1" "coder_tailscale" {
  metadata {
    name      = "coder-tailscale"
    namespace = kubernetes_namespace_v1.coder.metadata[0].name
  }

  spec {
    ingress_class_name = "tailscale"
    default_backend {
      service {
        name = "coder"
        port {
          number = 80
        }
      }
    }
    tls {
      hosts = [var.coder_tailnet_hostname]
    }
  }

  depends_on = [helm_release.tailscale_operator, helm_release.coder]
}
