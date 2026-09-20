// The endpoint Buck2 talks to (localhost:8980): REAPI CAS + action cache.
// Execute calls are forwarded to the scheduler (remote execution).
local common = import 'common.libsonnet';

{
  grpcServers: [{
    listenAddresses: [':8980'],
    authenticationPolicy: { allow: {} },
    // Buck2 uploads input-root Directory messages and blob batches larger than gRPC's 4 MiB default.
    maximumReceivedMessageSizeBytes: 64 * 1024 * 1024,
  }],
  schedulers: {
    '': {
      endpoint: {
        address: 'scheduler:8982',
        addMetadataJmespathExpression: {
          expression: |||
            {
              "build.bazel.remote.execution.v2.requestmetadata-bin": incomingGRPCMetadata."build.bazel.remote.execution.v2.requestmetadata-bin"
            }
          |||,
        },
      },
    },
  },
  executeAuthorizer: { allow: {} },
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  global: common.global,
  contentAddressableStorage: {
    backend: common.blobstore.contentAddressableStorage,
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
    findMissingAuthorizer: { allow: {} },
  },
  actionCache: {
    backend: common.blobstore.actionCache,
    getAuthorizer: { allow: {} },
    // Who may WRITE action results is the trust boundary of a shared cache: here anyone
    // who can reach the port. See docs (untrusted branches must not get putAuthorizer).
    putAuthorizer: { allow: {} },
  },
}
