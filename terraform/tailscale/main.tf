# The tailnet's policy file. This resource owns the whole file: anything not written here is removed on the next apply, so edit the
# policy here, not in the admin console. It is the Tailscale default (everyone can reach everything, SSH to your own devices in check
# mode) plus the two tags the Kubernetes operator needs (../platform/tailscale.tf):
#   tag:k8s-operator  the operator's own device (its OAuth client carries this tag)
#   tag:k8s           the proxy devices the operator creates for Ingresses and Services, owned by the operator

resource "tailscale_acl" "policy" {
  # The file already exists (the default); adopt it. Its content is reproduced below, so nothing is lost.
  overwrite_existing_content = true

  acl = jsonencode({
    tagOwners = {
      "tag:k8s-operator" = []
      "tag:k8s"          = ["tag:k8s-operator"]
    }

    grants = [
      { src = ["*"], dst = ["*"], ip = ["*"] },
    ]

    ssh = [
      {
        action = "check"
        src    = ["autogroup:member"]
        dst    = ["autogroup:self"]
        users  = ["autogroup:nonroot", "root"]
      },
    ]
  })
}
