terraform {
  required_version = ">= 1.10.0"

  required_providers {
    helm = {
      source  = "hashicorp/helm"
      version = "~> 3.2.0"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 3.2"
    }
  }

  # Partial configuration, see ../cluster/backend.hcl.example (use a different key, for example buckroot/platform.tfstate).
  backend "s3" {}
}
