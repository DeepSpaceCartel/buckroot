{{/* The environment of files/drain.sh for one pool's worker pod (the preStop of all three containers). args: dict "root" $ "pool" <name> */}}
{{- define "bb.drainEnv" -}}
{{- $props := .root.Values.platformProperties -}}
{{- $queue := dict "platformQueueName" (dict "platform" (dict "properties" $props)) -}}
{{- $executing := dict "executing" (dict "sizeClassQueueName" $queue) -}}
- name: POD_NAME
  valueFrom: { fieldRef: { fieldPath: metadata.name } }
- name: ADMIN
  value: {{ printf "http://scheduler-%s:7982" .pool | quote }}
- name: QUEUE
  value: {{ $queue | toJson | urlquery | quote }}
- name: EXECUTING
  value: {{ $executing | toJson | urlquery | quote }}
- name: DRAIN_TIMEOUT
  value: {{ .root.Values.workerDrainTimeoutSeconds | quote }}
- name: FALLBACK
  value: {{ .root.Values.workerTerminationDelaySeconds | quote }}
{{- end -}}

{{/* preStop: drain, then wait for the running action. */}}
{{- define "bb.drainHook" -}}
preStop: { exec: { command: [/tools/busybox, sh, /drain/drain.sh] } }
{{- end -}}
