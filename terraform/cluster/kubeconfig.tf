# Make `kubectl` work without KUBECONFIG: the module writes the cluster's kubeconfig to ~/.kube/buckroot.yaml, and this merges it
# into ~/.kube/config (its context becomes the current one). The previous ~/.kube/config is kept as config.bak-buckroot.
# It runs on the machine that applies, needs `kubectl` there, and never fails the apply (the cluster already exists by then):
# the fallback is `export KUBECONFIG=~/.kube/buckroot.yaml`.

resource "terraform_data" "kubeconfig" {
  triggers_replace = [sha256(module.kubernetes.kubeconfig)]

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    on_failure  = continue
    command     = <<-EOT
      set -eu
      mkdir -p ~/.kube && touch ~/.kube/config
      cp ~/.kube/config ~/.kube/config.bak-buckroot
      KUBECONFIG=~/.kube/buckroot.yaml:~/.kube/config kubectl config view --flatten > ~/.kube/config.new
      chmod 600 ~/.kube/config.new && mv ~/.kube/config.new ~/.kube/config
      echo "kubectl now uses the buckroot cluster (context $(kubectl config current-context))"
    EOT
  }
}
