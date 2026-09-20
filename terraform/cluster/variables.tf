variable "environment" {
  description = "Short name used in resource names and labels."
  type        = string
  default     = "dev"
}

locals {
  # Human-readable name => Hetzner Cloud location id. https://docs.hetzner.com/cloud/general/locations/
  hcloud_locations = {
    Nuremberg   = "nbg1"
    Falkenstein = "fsn1"
    Helsinki    = "hel1"
    Ashburn     = "ash"
    Hillsboro   = "hil"
  }
}

variable "hcloud_location" {
  description = "Hetzner Cloud location (id) of the whole cluster. Not every server type exists in every location: check `hcloud server-type list` first."
  type        = string
  default     = "hil" # Hillsboro

  validation {
    condition     = contains(values(local.hcloud_locations), var.hcloud_location)
    error_message = "hcloud_location must be one of: ${join(", ", values(local.hcloud_locations))}."
  }
}

variable "hcloud_token" {
  description = "Hetzner Cloud API token for the project that holds this cluster. Set via TF_VAR_hcloud_token, not a tfvars file."
  type        = string
  sensitive   = true
}

variable "control_nodes_count" {
  description = "Talos control-plane nodes (odd, at most 9). One keeps the cost down; three is highly available."
  type        = number
  default     = 1
}

# Server types. All x86: the tool baseline and the vendor host tools are x86-64 (Hetzner's arm64 CAX types are out).
variable "control_node_type" {
  type    = string
  default = "cpx21"
}

variable "platform_node_type" {
  description = "The one always-on worker node: Buildbarn storage, frontend, schedulers, portal, Postgres, Coder, KEDA, Prometheus."
  type        = string
  default     = "cpx41" # 8 vCPU, 16 GB. cpx31 (4 vCPU, 8 GB) is the floor.
}

variable "workers_shared_type" {
  description = "Cheap shared-vCPU workers: for iteration, timings are noisy."
  type        = string
  default     = "cpx51" # 16 vCPU, 32 GB
}

variable "workers_shared_max" {
  type    = number
  default = 8
}

variable "workers_dedicated_type" {
  description = "Dedicated-vCPU workers: consistent timings, for measured runs."
  type        = string
  default     = "ccx33" # 8 dedicated vCPU, 32 GB
}

variable "workers_dedicated_max" {
  type    = number
  default = 4
}

variable "coder_workspaces_type" {
  type    = string
  default = "cpx31"
}

variable "coder_workspaces_max" {
  type    = number
  default = 2
}
