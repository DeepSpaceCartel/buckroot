# Coder: cloud development workspaces. Postgres (bitnami chart) + the coder chart, following the reference layout of
# rts-terraform's modules/coder. Reached by `kubectl port-forward` until a gateway and DNS are added; workspace agents
# reach it at its in-cluster address.

resource "kubernetes_namespace_v1" "coder" {
  metadata {
    name = "coder"
  }
}

resource "kubernetes_namespace_v1" "workspaces" {
  metadata {
    name = "coder-workspaces"
  }
}

locals {
  coder_db_url = "postgres://coder:${urlencode(var.coder_postgres_password)}@postgresql.${kubernetes_namespace_v1.coder.metadata[0].name}.svc.cluster.local:5432/coder?sslmode=disable"
}

resource "helm_release" "postgresql" {
  name      = "postgresql"
  namespace = kubernetes_namespace_v1.coder.metadata[0].name

  repository = "oci://registry-1.docker.io/bitnamicharts"
  chart      = "postgresql"
  version    = var.postgresql_chart_version

  timeout = 900
  atomic  = true

  set = [
    # The free bitnami/* images stopped being published in 2025; bitnamilegacy/* is where the last ones live.
    { name = "image.repository", value = "bitnamilegacy/postgresql" },
    { name = "auth.username", value = "coder" },
    { name = "auth.database", value = "coder" },
    { name = "primary.persistence.size", value = "10Gi" },
  ]

  set_sensitive = [
    { name = "auth.password", value = var.coder_postgres_password },
  ]
}

resource "kubernetes_secret_v1" "coder_db" {
  metadata {
    name      = "coder-db-url"
    namespace = kubernetes_namespace_v1.coder.metadata[0].name
  }

  data = {
    url = local.coder_db_url
  }

  depends_on = [helm_release.postgresql]
}

resource "helm_release" "coder" {
  name      = "coder"
  namespace = kubernetes_namespace_v1.coder.metadata[0].name

  repository = "oci://ghcr.io/coder/chart"
  chart      = "coder"
  version    = var.coder_chart_version

  timeout = 900
  atomic  = true

  values = [yamlencode({
    coder = {
      service      = { type = "ClusterIP" }
      serviceAccount = {
        # Workspaces are provisioned into their own namespace.
        workspaceNamespaces = [{ name = kubernetes_namespace_v1.workspaces.metadata[0].name }]
      }
      env = [
        {
          name      = "CODER_PG_CONNECTION_URL"
          valueFrom = { secretKeyRef = { name = kubernetes_secret_v1.coder_db.metadata[0].name, key = "url" } }
        },
        { name = "CODER_ACCESS_URL", value = var.coder_access_url },
        # GitHub sign-in for members of these organisations (Coder's shared GitHub app); without this a GitHub login finds no user
        # and stops at "Signups are disabled". The admin account above still works with its password.
        { name = "CODER_OAUTH2_GITHUB_ALLOW_SIGNUPS", value = "true" },
        { name = "CODER_OAUTH2_GITHUB_ALLOWED_ORGS", value = join(",", var.coder_github_orgs) },
      ]
    }
  })]
}

# Creates the admin account server-side the moment the deployment is up, so the unauthenticated first-run screen is never
# exposed. Needs kubectl on the machine that applies this (as in the reference). Idempotent: "already exists" is success.
resource "terraform_data" "coder_admin_user" {
  triggers_replace = [var.coder_admin_username, var.coder_admin_email]

  provisioner "local-exec" {
    quiet   = true
    command = <<-EOT
      set -u
      i=0
      while true; do
        i=$((i + 1))
        OUT="$(kubectl exec deploy/coder -n coder -- env CODER_USERNAME="$ADMIN_USERNAME" CODER_EMAIL="$ADMIN_EMAIL" CODER_PASSWORD="$ADMIN_PASSWORD" coder server create-admin-user 2>&1)"
        RC=$?
        [ "$RC" -eq 0 ] && exit 0
        echo "$OUT" | grep -qiE "already (exists|in use|been created)|duplicate" && exit 0
        [ "$i" -ge 5 ] && { echo "$OUT" >&2; exit "$RC"; }
        sleep 5
      done
    EOT
    environment = {
      KUBECONFIG     = "${path.module}/../cluster/kubeconfig"
      ADMIN_USERNAME = var.coder_admin_username
      ADMIN_EMAIL    = var.coder_admin_email
      ADMIN_PASSWORD = var.coder_admin_password
    }
  }

  depends_on = [helm_release.coder]
}
