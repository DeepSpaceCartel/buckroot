# Infrastructure: Buildbarn and Coder on Hetzner Cloud

A Kubernetes cluster dedicated to buckroot development: Buildbarn (remote cache and remote execution) with autoscaled worker
pools, and Coder for workspaces. Talos on Hetzner Cloud, built with the `hcloud-k8s/kubernetes/hcloud` module.
Design and reasoning: [Kubernetes deployment guide](../docs/guides/kubernetes.md) and ADR-0015.

```
terraform/
  cluster/            the cluster: control plane, an always-on platform node, three autoscaled pools (0..N)
  platform/           what runs on it: Buildbarn (charts/buckroot-buildbarn), KEDA, Prometheus, Coder
  coder-templates/    the workspace template, as code
../charts/buckroot-buildbarn/    the Buildbarn Helm chart
```

## Pools

| Pool | Size | Purpose |
|---|---|---|
| control | static x1 | Talos control plane |
| platform | static x1 | Buildbarn storage, frontend, schedulers, portal, Postgres, Coder, KEDA, Prometheus |
| bb-workers-shared | 0..8 | Buildbarn workers, cheap shared vCPU (noisy timings) |
| bb-workers-dedicated | 0..4 | Buildbarn workers, dedicated vCPU (measured runs) |
| coder-workspaces | 0..2 | Coder workspace pods |

The autoscaled pools are empty until a pod needs them and are billed hourly only while a server exists. Server types are variables;
check availability in your location with `hcloud server-type list` (all x86: the tool baseline is x86-64).

## Apply

Requires `terraform` >= 1.10, `kubectl`, `helm`, a Hetzner Cloud project and API token, and an S3-compatible bucket for state.

```bash
export TF_VAR_hcloud_token=...                       # Hetzner Cloud API token
cd cluster
cp backend.hcl.example backend.hcl                    # edit: your state bucket
cp terraform.tfvars.example terraform.tfvars
terraform init -backend-config=backend.hcl && terraform apply

export KUBECONFIG=$PWD/kubeconfig && kubectl get nodes

cd ../platform                                        # same pattern: backend.hcl (a different key), terraform.tfvars
export TF_VAR_coder_admin_password=... TF_VAR_coder_postgres_password=...
terraform init -backend-config=backend.hcl && terraform apply
```

Then use it from a Coder workspace (`BR2_RE_ENDPOINT` is set there):
`scripts/br2 viewcheck --mode remote` and `scripts/br2 build --variant wrapped --mode remote-cache`.
Enable worker autoscaling by setting `worker_scaling_queries` once the scheduler's queue metric is known (see the chart's `values.yaml`).

## Tear down

`platform/teardown.sh`, then `terraform destroy` in `platform/`, then in `cluster/`.

## Checks (no cloud needed)

```bash
for d in cluster platform coder-templates; do (cd $d && terraform init -backend=false && terraform validate); done
helm lint ../charts/buckroot-buildbarn && helm template t ../charts/buckroot-buildbarn >/dev/null
```

## Not done yet

Public access (a gateway, TLS and DNS for Coder and the Buildbarn UIs: reach them by `kubectl port-forward`, see `terraform output`),
network policies and other internal cluster security (single-tenant for now), and external access to Buildbarn with client authentication.
