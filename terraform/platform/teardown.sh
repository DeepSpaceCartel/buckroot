#!/usr/bin/env bash
#
# Clears out what Terraform does not know about, so `terraform destroy` in ../cluster does not hang.
#
# The autoscaler creates and deletes Hetzner servers itself; they are not Terraform resources. Hetzner refuses to delete a
# network with servers still attached, so destroying the cluster stalls while any autoscaled node exists. Those nodes exist
# only because pods need them (Buildbarn workers, Coder workspaces). Remove those pods and the autoscaler scales the nodes
# back to zero on its own within a few minutes.
#
# Order: this script, then `terraform destroy` in ../platform, then `terraform destroy` in ../cluster.
# Prompts before every deletion; nothing runs unattended.
set -uo pipefail
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/buckroot.yaml}"

confirm() { read -r -p "  $1 [y/N] " reply </dev/tty; [[ "$reply" =~ ^[Yy]$ ]]; }

echo "Buildbarn workers:"
if kubectl get ns buildbarn >/dev/null 2>&1 && confirm "scale every worker Deployment to 0 (and pause KEDA on them)?"; then
  kubectl -n buildbarn delete scaledobject --all --ignore-not-found
  for d in $(kubectl -n buildbarn get deploy -o name | grep worker-); do kubectl -n buildbarn scale "$d" --replicas=0; done
fi

echo "Coder workspaces:"
if kubectl get ns coder-workspaces >/dev/null 2>&1 && confirm "delete every workspace pod, deployment and claim in coder-workspaces?"; then
  kubectl -n coder-workspaces delete deploy,pvc --all --ignore-not-found
fi

echo "Waiting for autoscaled nodes to go (the autoscaler removes empty nodes after its scale-down delay):"
while true; do
  n=$(kubectl get nodes -l 'buckroot.dev/pool=nodes' --no-headers 2>/dev/null | wc -l)
  echo "  autoscaled nodes left: $n"
  [ "$n" -eq 0 ] && break
  sleep 30
done
echo "Done. Now: terraform destroy in ../platform, then in ../cluster."
