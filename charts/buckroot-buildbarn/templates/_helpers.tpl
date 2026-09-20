{{/* Names and labels */}}
{{- define "bb.labels" -}}
app.kubernetes.io/name: buckroot-buildbarn
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* The static jsonnet files of the toolkit, as ConfigMap data (env.libsonnet is added per component). */}}
{{- define "bb.staticConfig" -}}
{{- range $path, $_ := .Files.Glob "files/config/*" }}
{{ base $path }}: |
{{ $.Files.Get $path | indent 2 }}
{{- end }}
{{- end -}}

{{/* env.libsonnet. args: dict "root" $ "workerPool" "<name or empty>" */}}
{{- define "bb.env" -}}
{{- $root := .root -}}
{{- $v := $root.Values -}}
{{- $pool := .workerPool -}}
{{- $first := "" -}}
{{- range $name, $p := $v.pools }}{{ if and $p.enabled (not $first) }}{{ $first = $name }}{{ end }}{{ end -}}
{
  storageAddress: 'storage:8981',
  {{- if $pool }}
  schedulerWorkerAddress: {{ printf "scheduler-%s:8983" $pool | squote }},
  workerPool: {{ $pool | squote }},
  workerConcurrency: {{ (index $v.pools $pool).worker.concurrency }},
  workerCacheBytes: {{ (index $v.pools $pool).worker.cacheGiB }} * 1024 * 1024 * 1024,
  noWorkersTimeout: {{ (index $v.pools $pool).noWorkersTimeout | squote }},
  {{- else }}
  schedulerWorkerAddress: {{ printf "scheduler-%s:8983" $first | squote }},
  noWorkersTimeout: {{ (index $v.pools $first).noWorkersTimeout | squote }},
  {{- end }}
  schedulerStateAddress: {{ printf "scheduler-%s:8984" ($v.portal.pool | default $first) | squote }},
  schedulers: {
    {{- range $name, $p := $v.pools }}{{ if $p.enabled }}
    {{ $p.instancePrefix | squote }}: {{ printf "scheduler-%s:8982" $name | squote }},
    {{- end }}{{ end }}
  },
  casSizeBytes: {{ $v.storage.casSizeGiB }} * 1024 * 1024 * 1024,
  casKeyMapBytes: 400 * 1024 * 1024,
  acSizeBytes: {{ $v.storage.acSizeGiB }} * 1024 * 1024 * 1024,
  acKeyMapBytes: 16 * 1024 * 1024,
  workerCacheFiles: 100000,
  platformProperties: {{ toJson $v.platformProperties }},
  diagnosticsAddress: {{ printf ":%v" $v.diagnosticsPort | squote }},
  postgresConnection: {{ printf "postgresql://app:%s@postgres:5432/app" $v.portal.postgres.password | squote }},
  portalGrpcBackendUrl: 'grpc://localhost:8082',
}
{{- end -}}

{{/* A ConfigMap with the static files and this component's env. args: dict "root" $ "name" <cm name> "workerPool" <...> */}}
{{- define "bb.configmap" -}}
apiVersion: v1
kind: ConfigMap
metadata:
  name: {{ .name }}
  labels:
    {{- include "bb.labels" .root | nindent 4 }}
data:
  {{- include "bb.staticConfig" .root | indent 2 }}
  env.libsonnet: |
{{ include "bb.env" (dict "root" .root "workerPool" .workerPool) | indent 4 }}
{{- end -}}
