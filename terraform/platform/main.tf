# Everything deployed onto the cluster (../cluster). A separate state and apply, so the helm and kubernetes providers below
# are configured from an already-known value (the cluster state's kubeconfig_data output).
#
# Apply order: ../cluster, then this state, then ../coder-templates. Verify access before applying this one:
#   export KUBECONFIG=../cluster/kubeconfig
#   kubectl get nodes

data "terraform_remote_state" "cluster" {
  backend = "s3"
  config = {
    bucket = "rts-terraform-admin"
    key    = "buckroot/cluster.tfstate"
    region = "us-east-1"
  }
}

locals {
  kubeconfig = data.terraform_remote_state.cluster.outputs.kubeconfig_data
}

provider "helm" {
  kubernetes = {
    host                   = local.kubeconfig.server
    client_certificate     = local.kubeconfig.cert
    client_key             = local.kubeconfig.key
    cluster_ca_certificate = local.kubeconfig.ca
  }
}

provider "kubernetes" {
  host                   = local.kubeconfig.server
  client_certificate     = local.kubeconfig.cert
  client_key             = local.kubeconfig.key
  cluster_ca_certificate = local.kubeconfig.ca
}
