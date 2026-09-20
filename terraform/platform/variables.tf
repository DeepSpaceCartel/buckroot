variable "environment" {
  description = "Must match ../cluster's environment."
  type        = string
  default     = "dev"
}

# --- Buildbarn ---------------------------------------------------------------------------------------------------------

variable "runner_image" {
  description = "The worker tool baseline (toolkit/infra/buildbarn/runner/Dockerfile), ideally pinned by digest: ghcr.io/deepspacecartel/buckroot-worker@sha256:..."
  type        = string
  default     = "ghcr.io/deepspacecartel/buckroot-worker:latest"
}

variable "cas_size_gib" {
  description = "Size of the content-addressable storage. One blob has to fit in one block (size / 22): 100 GiB gives 4.5 GiB blocks."
  type        = number
  default     = 100
}

variable "worker_scaling_queries" {
  description = <<-EOT
    Prometheus query per pool (keys: shared, dedicated) that returns the number of queued + executing operations of that pool's scheduler.
    Empty disables worker autoscaling (workers then stay at their replica count). Read the metric names from a scheduler's /metrics first.
  EOT
  type        = map(string)
  default     = {}
}

# --- Chart versions (pinned explicitly, check for newer ones when upgrading) ---------------------------------------------

variable "keda_chart_version" {
  type    = string
  default = "2.17.2"
}

variable "prometheus_chart_version" {
  type    = string
  default = "27.20.0"
}

variable "postgresql_chart_version" {
  description = "bitnami/postgresql chart. Must stay at a release whose default image is <= 17.6.0: the free bitnami images were frozen in bitnamilegacy."
  type        = string
  default     = "16.7.27"
}

variable "coder_chart_version" {
  type    = string
  default = "2.37.0"
}

# --- Coder ---------------------------------------------------------------------------------------------------------------

variable "coder_access_url" {
  description = "URL workspace agents use to reach Coder. The in-cluster address works for workspaces on this cluster; set a public URL when Coder is exposed."
  type        = string
  default     = "http://coder.coder.svc.cluster.local"
}

variable "coder_admin_username" {
  type    = string
  default = "admin"
}

variable "coder_admin_email" {
  type    = string
  default = "admin@buckroot.local"
}

variable "coder_admin_password" {
  description = "Set via TF_VAR_coder_admin_password, not a tfvars file."
  type        = string
  sensitive   = true
}

variable "coder_postgres_password" {
  description = "Set via TF_VAR_coder_postgres_password, not a tfvars file."
  type        = string
  sensitive   = true
}
