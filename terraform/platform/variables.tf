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

variable "worker_autoscaling" {
  description = <<-EOT
    Scale each worker pool with KEDA on the queue depth of its scheduler (scale to zero when idle; the node autoscaler then removes
    the empty nodes). When true, `worker_replicas` is ignored. Set false to hold a fixed number of workers.
  EOT
  type        = bool
  default     = true
}

variable "worker_scaling_queries" {
  description = "Override the chart's default queue-depth query per pool (keys: shared, dedicated, legacy). Empty uses the default."
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

# --- Tailscale ---------------------------------------------------------------------------------------------------------

variable "tailscale_client_id" {
  description = "Tailscale OAuth client id (Devices Core and Auth Keys, write; tag:k8s-operator). Set via TF_VAR_tailscale_client_id."
  type        = string
}

variable "tailscale_client_secret" {
  description = "Tailscale OAuth client secret. Set via TF_VAR_tailscale_client_secret."
  type        = string
  sensitive   = true
}

variable "tailscale_chart_version" {
  type    = string
  default = "1.102.4"
}

variable "coder_tailnet_hostname" {
  description = "Coder's machine name on the tailnet: https://<this>.<tailnet>.ts.net"
  type        = string
  default     = "coder"
}

variable "coder_github_orgs" {
  description = "GitHub organisations whose members can sign in to Coder with GitHub."
  type        = list(string)
  default     = ["DeepSpaceCartel"]
}

variable "worker_replicas" {
  description = <<-EOT
    Fixed number of worker pods per pool (keys: shared, dedicated, legacy) while `worker_autoscaling` is false. A shared node runs two workers, so
    shared = 4 needs two nodes. Costs money while non-zero (a cpx51 is about 0.45 EUR/h): set it for a run, then back to {}.
  EOT
  type        = map(number)
  default     = {}
}

variable "buildbarn_tailnet_hostname" {
  description = "The Buildbarn frontend's machine name on the tailnet: grpc://<this>.<tailnet>.ts.net:8980"
  type        = string
  default     = "buildbarn"
}

variable "golden_dl_gib" {
  description = "Size of the download cache volume of the golden Jobs (Buildroot BR2_DL_DIR, all projects)."
  type        = number
  default     = 60
}
