terraform {
  required_version = ">= 1.10.0"

  required_providers {
    coderd = {
      source  = "coder/coderd"
      version = ">= 0.0.10"
    }
  }

  # Partial configuration, see ../cluster/backend.hcl.example (key, for example buckroot/coder-templates.tfstate).
  backend "s3" {}
}
