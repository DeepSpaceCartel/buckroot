// Shared Buildbarn configuration. Trimmed from buildbarn/bb-deployments (docker-compose),
// with a single storage shard instead of two.
local storage = { grpc: { client: { address: 'storage:8981' } } };

{
  blobstore: {
    contentAddressableStorage: storage,
    actionCache: {
      // An AC entry is only served if everything it references is still in the CAS,
      // so an evicted blob turns into a cache miss instead of a broken build.
      completenessChecking: {
        backend: storage,
        maximumTotalTreeSizeBytes: 64 * 1024 * 1024,
      },
    },
  },
  maximumMessageSizeBytes: 64 * 1024 * 1024,
  global: {
    diagnosticsHttpServer: {
      httpServers: [{
        listenAddresses: [':80'],
        authenticationPolicy: { allow: {} },
      }],
      enablePrometheus: true,
      enablePprof: true,
      enableActiveSpans: true,
    },
  },
}
