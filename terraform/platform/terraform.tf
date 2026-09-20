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

  # State lives in the organisation's S3 bucket (credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, see ../.env.1password).
  # One key per state; a backend block cannot use variables, so the bucket is repeated in ../platform and ../coder-templates.
  backend "s3" {
    bucket       = "rts-terraform-admin"
    key          = "buckroot/platform.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}
