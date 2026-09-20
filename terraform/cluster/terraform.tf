terraform {
  required_version = ">= 1.10.0"

  required_providers {
    hcloud = {
      source  = "hetznercloud/hcloud"
      version = ">= 1.68, < 2.0"
    }
  }

  # Partial configuration: state lives in an S3-compatible bucket whose name and credentials are supplied when
  # initialising, never committed:
  #   terraform init -backend-config=backend.hcl        (see backend.hcl.example)
  backend "s3" {}
}
