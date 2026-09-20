# Charts

`buckroot-buildbarn` deploys Buildbarn (remote cache and remote execution) on Kubernetes: storage, frontend, one scheduler and one
autoscalable worker pool per entry of `pools`, and the portal. The Buildbarn jsonnet is the toolkit's, unchanged: run
`charts/buckroot-buildbarn/sync-config.sh` after editing `toolkit/infra/buildbarn/config/`, and the chart renders `env.libsonnet` from
`values.yaml`. Check with `helm lint` and `helm template` (see `ci/keda-values.yaml` for the scaling variant).
