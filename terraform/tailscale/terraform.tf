terraform {
  required_version = ">= 1.10.0"

  required_providers {
    tailscale = {
      source  = "tailscale/tailscale"
      version = ">= 0.20"
    }
  }

  # State lives in the organisation's S3 bucket (credentials: AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, see ../.env.1password).
  backend "s3" {
    bucket       = "rts-terraform-admin"
    key          = "buckroot/tailscale.tfstate"
    region       = "us-east-1"
    use_lockfile = true
    encrypt      = true
  }
}

# Credentials: an OAuth client with the Policy File scope (write), from the environment:
# TAILSCALE_OAUTH_CLIENT_ID and TAILSCALE_OAUTH_CLIENT_SECRET (see ../.env.tailscale.1password).
provider "tailscale" {
  scopes = ["policy_file"]
}
