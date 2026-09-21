# Infrastructure: Buildbarn and Coder on Hetzner Cloud

A Kubernetes cluster dedicated to buckroot development: Buildbarn (remote cache and remote execution) with autoscaled worker
pools, and Coder for workspaces. Talos on Hetzner Cloud, built with the `hcloud-k8s/kubernetes/hcloud` module.
Design and reasoning: [Kubernetes deployment guide](../docs/guides/kubernetes.md) and ADR-0015.

```
terraform/
  cluster/            the cluster: a schedulable control node and one autoscaled pool (0..4), one server type
  platform/           what runs on it: Buildbarn (charts/buckroot-buildbarn), KEDA, Prometheus, Coder
  coder-templates/    the workspace template, as code
  tailscale/          the tailnet policy (tags for the Kubernetes operator)
../charts/buckroot-buildbarn/    the Buildbarn Helm chart
```

## Pools

| Pool | Size | Purpose |
|---|---|---|
| control | static x1, `cpx51` | Talos control plane, schedulable: platform pods and workers run here too |
| nodes | 0..4, `cpx51` | one autoscaled pool, no taints: platform pods, Coder workspaces, Buildbarn workers (two per node) |

One server type and no taints, because the Hetzner project's server limit is 5 (a new account cannot request more) and a
server reserved for one kind of pod is a wasted slot; see [ADR-0016](../docs/decisions/0016-one-node-pool.md). A node exists only
while a pod needs it and is billed hourly. Server types are variables; check availability in your location with
`hcloud server-type list` (all x86: the tool baseline is x86-64).

## Apply

Requires `terraform` >= 1.10, `kubectl`, `helm`, and 1Password's `op` (or the same variables exported by hand).

Everything is baked in: the state backend (S3 bucket `rts-terraform-admin`, one key per state), the server types, pool sizes and location
(defaults in each `variables.tf`). Only secrets are inputs, and they are 1Password references, so there are no files to copy or edit:
[`.env.1password`](.env.1password) (state backend, Hetzner token; every state), [`.env.platform.1password`](.env.platform.1password) and
[`.env.tailscale.1password`](.env.tailscale.1password). Authenticate `op` with `eval $(op signin)` or an
`OP_SERVICE_ACCOUNT_TOKEN` (read access to the vault is enough).

```bash
E="op run --env-file=$PWD/.env.1password"              # from terraform/
(cd cluster && $E -- terraform init && $E -- terraform apply)   # also merges the cluster into ~/.kube/config: `kubectl get nodes` just works
(cd platform && P="$E --env-file=$PWD/../.env.platform.1password"; $P -- terraform init && $P -- terraform apply)
```

`coder-templates/` needs a Coder API token, which does not exist until Coder is up. It is not stored anywhere: log in as the admin user
for a session token and give it to that one apply (with a port-forward to Coder, or over Tailscale):

```bash
kubectl -n coder port-forward svc/coder 8080:80 &
cd coder-templates
op run --env-file=$PWD/../.env.1password --env-file=$PWD/../.env.platform.1password -- bash -c '
  export TF_VAR_coder_token=$(curl -s -X POST http://127.0.0.1:8080/api/v2/users/login -H "Content-Type: application/json" \
    -d "{\"email\":\"admin@buckroot.local\",\"password\":\"$TF_VAR_coder_admin_password\"}" | python3 -c "import sys,json; print(json.load(sys.stdin)[\"session_token\"])")
  terraform init && terraform apply'
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
