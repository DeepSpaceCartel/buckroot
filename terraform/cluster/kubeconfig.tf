# Make `kubectl` work without KUBECONFIG: the module writes the cluster's kubeconfig next to this file (git-ignored), and this
# installs it as ~/.kube/buckroot.yaml and merges it into ~/.kube/config (its context becomes the current one). The previous
# ~/.kube/config is kept as config.bak-buckroot. Same for the Talos config: ~/.talos/buckroot.yaml.
# It runs on the machine that applies, needs `kubectl` there, and never fails the apply (the cluster already exists by then):
# the fallback is `export KUBECONFIG=<this directory>/kubeconfig`.

resource "terraform_data" "kubeconfig" {
  triggers_replace = [sha256(module.kubernetes.kubeconfig)]
  depends_on       = [module.kubernetes]

  provisioner "local-exec" {
    interpreter = ["/bin/bash", "-c"]
    on_failure  = continue
    working_dir = path.module
    command     = <<-EOT
      set -eu
      mkdir -p ~/.kube ~/.talos && touch ~/.kube/config
      cp kubeconfig ~/.kube/buckroot.yaml && cp talosconfig ~/.talos/buckroot.yaml
      chmod 600 ~/.kube/buckroot.yaml ~/.talos/buckroot.yaml
      cp ~/.kube/config ~/.kube/config.bak-buckroot
      KUBECONFIG=~/.kube/buckroot.yaml:~/.kube/config kubectl config view --flatten > ~/.kube/config.new
      chmod 600 ~/.kube/config.new && mv ~/.kube/config.new ~/.kube/config
      echo "kubectl now uses the buckroot cluster (context $(kubectl config current-context))"
    EOT
  }
}
