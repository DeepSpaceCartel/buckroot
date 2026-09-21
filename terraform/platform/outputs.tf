output "buildbarn_endpoint" {
  description = "The remote cache and execution endpoint, for BR2_RE_ENDPOINT inside the cluster (workspaces, jobs)."
  value       = "grpc://frontend.${kubernetes_namespace_v1.buildbarn.metadata[0].name}.svc.cluster.local:8980"
}

output "buildbarn_ui" {
  description = "Web UIs, by port-forward: scheduler admin and portal."
  value = {
    scheduler_shared    = "kubectl -n buildbarn port-forward svc/scheduler-shared 7982:7982   # http://127.0.0.1:7982/"
    scheduler_dedicated = "kubectl -n buildbarn port-forward svc/scheduler-dedicated 7983:7982   # http://127.0.0.1:7983/"
    portal              = "kubectl -n buildbarn port-forward svc/portal 8081:8081   # http://127.0.0.1:8081/"
  }
}

output "coder_ui" {
  description = "Coder, over Tailscale."
  value       = "https://${var.coder_tailnet_hostname}.<your-tailnet>.ts.net (Tailscale), or: kubectl -n coder port-forward svc/coder 8080:80"
}
