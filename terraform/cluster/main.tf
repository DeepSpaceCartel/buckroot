# The cluster itself: Talos on Hetzner Cloud, nothing deployed into it (that is ../platform, a separate state so
# its helm/kubernetes providers are configured from a value that is already known; see ../platform/main.tf).
#
# Node pools
#   control              static   Talos control plane
#   platform             static   the always-on node: Buildbarn storage/frontend/schedulers/portal, Coder, KEDA, Prometheus
#   bb-workers-shared    0..N     Buildbarn workers, cheap shared vCPU
#   bb-workers-dedicated 0..M     Buildbarn workers, dedicated vCPU (measured runs)
#   coder-workspaces     0..K     Coder workspace pods
# The three autoscaled pools are empty until a pod needs them, and billed hourly only while a server exists.
# Worker pools carry the taint buckroot-worker=true:NoSchedule; only the Buildbarn worker pods tolerate it.

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

  worker_nodepools = [
    {
      name     = "platform"
      type     = var.platform_node_type
      location = var.hcloud_location
      count    = 1
      labels   = { "buckroot.dev/pool" = "platform" }
    }
  ]

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
      name     = "bb-workers-shared"
      type     = var.workers_shared_type
      location = var.hcloud_location
      min      = 0
      max      = var.workers_shared_max
      labels   = { "buckroot.dev/pool" = "bb-workers-shared" }
      taints   = ["buckroot-worker=true:NoSchedule"]
    },
    {
      name     = "bb-workers-dedicated"
      type     = var.workers_dedicated_type
      location = var.hcloud_location
      min      = 0
      max      = var.workers_dedicated_max
      labels   = { "buckroot.dev/pool" = "bb-workers-dedicated" }
      taints   = ["buckroot-worker=true:NoSchedule"]
    },
    {
      name     = "coder-workspaces"
      type     = var.coder_workspaces_type
      location = var.hcloud_location
      min      = 0
      max      = var.coder_workspaces_max
      labels   = { "coder-workspace" = "true", "buckroot.dev/pool" = "coder-workspaces" }
      taints   = ["coder-workspace=true:NoSchedule"]
    },
  ]

  # Talos and the Kubernetes API are reachable only from the machine that applies this.
  firewall_use_current_ipv4 = true
  firewall_use_current_ipv6 = true

  talos_backup_enabled = false

  # hcloud CSI (volumes for Buildbarn storage, Postgres, workspaces) is on by default in the module.
}
