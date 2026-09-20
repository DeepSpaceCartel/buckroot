# The buckroot workspace template, managed as code through the coderd provider.
#
# Needs a Coder API token: create one in the Coder UI (Account > Tokens) or with `coder tokens create`, and pass it as
# TF_VAR_coder_token. With Coder reached by port-forward, use its local address as coder_url.

variable "coder_url" {
  description = "Coder's URL as reachable from this machine (a port-forward: kubectl -n coder port-forward svc/coder 8080:80)."
  type        = string
  default     = "http://127.0.0.1:8080"
}

variable "coder_token" {
  description = "Coder API token. Set via TF_VAR_coder_token."
  type        = string
  sensitive   = true
}

provider "coderd" {
  url   = var.coder_url
  token = var.coder_token
}

resource "coderd_template" "buckroot" {
  name         = "buckroot-workspace"
  display_name = "buckroot workspace"
  description  = "Build Buildroot projects with Buck2 against the cluster's Buildbarn (remote cache and execution)."

  versions = [{
    name      = "v1"
    directory = "${path.module}/templates/buckroot-workspace"
    active    = true
  }]
}
