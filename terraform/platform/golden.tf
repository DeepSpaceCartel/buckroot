# The golden build runs as a Kubernetes Job (`br2 golden --k8s`, toolkit/scripts/br2). Its downloads persist here: Buildroot's
# BR2_DL_DIR is a complete, reusable download cache, so a second golden of any project downloads nothing and a retry after a
# rate-limited download picks up where it stopped. Shared by all projects (files are versioned). A Hetzner volume is single-attach,
# so one golden Job runs at a time; a second waits in Pending until the first finishes.
resource "kubernetes_persistent_volume_claim_v1" "golden_dl" {
  metadata {
    name      = "golden-dl"
    namespace = kubernetes_namespace_v1.buildbarn.metadata[0].name
  }
  spec {
    access_modes = ["ReadWriteOnce"]
    resources {
      requests = { storage = "${var.golden_dl_gib}Gi" }
    }
  }
  wait_until_bound = false # bound on first use (WaitForFirstConsumer)
}
