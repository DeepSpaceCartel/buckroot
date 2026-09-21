# The cluster itself: Talos on Hetzner Cloud, nothing deployed into it (that is ../platform, a separate state so
# its helm/kubernetes providers are configured from a value that is already known; see ../platform/main.tf).
#
# Node pools (the project's server limit is 5, so every server must be usable for anything):
#   control   static, 1   Talos control plane, schedulable: platform pods and workers land here too
#   nodes     0..4        one autoscaled pool, no taints or labels to match: platform pods, Coder workspaces, Buildbarn workers
# Everything is one server type; a node exists only while a pod needs it and is billed hourly.

module "kubernetes" {
  source  = "hcloud-k8s/kubernetes/hcloud"
  version = "5.6.1"

  cluster_name = "buckroot-${var.environment}"
  hcloud_token = var.hcloud_token

  cluster_delete_protection = false

  cluster_kubeconfig_path  = "${path.module}/kubeconfig"
  cluster_talosconfig_path = "${path.module}/talosconfig"

  control_plane_nodepools = [
    { name = "control", type = var.control_node_type, location = var.hcloud_location, count = var.control_nodes_count }
  ]

  # No static workers: the control plane takes pods, the autoscaled pool takes the rest.
  cluster_allow_scheduling_on_control_planes = true

  cluster_autoscaler_enabled = true

  # Scale-in soon after a node is empty: the pod removal that empties it is done by KEDA, and only idle workers are ever
  # removed (see charts/buckroot-buildbarn), so a short delay does not risk running actions.
  cluster_autoscaler_helm_values = {
    extraArgs = {
      "scale-down-unneeded-time"         = "4m"
      "scale-down-delay-after-add"       = "3m"
      "scale-down-utilization-threshold" = "0.5"
    }
  }

  cluster_autoscaler_nodepools = [
    {
      name     = "nodes"
      type     = var.nodes_type
      location = var.hcloud_location
      min      = 0
      max      = var.nodes_max
      labels   = { "buckroot.dev/pool" = "nodes" }
    },
  ]

  # Talos and the Kubernetes API are reachable only from the machine that applies this.
  firewall_use_current_ipv4 = true
  firewall_use_current_ipv6 = true

  talos_backup_enabled = false

  # hcloud CSI (volumes for Buildbarn storage, Postgres, workspaces) is on by default in the module.
}
