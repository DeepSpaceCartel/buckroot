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

Requires `terraform` >= 1.10, `kubectl`, `helm`, and 1Password's `op` (or the same variables exported by hand).

Everything is baked in: the state backend (S3 bucket `rts-terraform-admin`, one key per state), the server types, pool sizes and location
(defaults in each `variables.tf`). Only secrets are inputs, and they are 1Password references in [`.env.1password`](.env.1password), so there
are no files to copy or edit. Sign in once with `eval $(op signin)`.

```bash
alias tf='op run --env-file=$PWD/.env.1password -- terraform'    # from terraform/
(cd cluster && tf init && tf apply)     # also merges the cluster into ~/.kube/config: `kubectl get nodes` just works
(cd platform && tf init && tf apply)
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
