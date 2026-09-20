# Consumed by ../platform through a terraform_remote_state data source: its providers are then configured from a
# value that is already known instead of one computed in the same apply that creates the cluster.

output "kubeconfig_data" {
  description = "Structured kubeconfig data for the helm, kubernetes and kubectl providers."
  value       = module.kubernetes.kubeconfig_data
  sensitive   = true
}

output "kubeconfig" {
  description = "Raw kubeconfig (also written to ./kubeconfig, which is git-ignored)."
  value       = module.kubernetes.kubeconfig
  sensitive   = true
}

output "talosconfig" {
  description = "Raw Talos configuration (also written to ./talosconfig, which is git-ignored)."
  value       = module.kubernetes.talosconfig
  sensitive   = true
}
