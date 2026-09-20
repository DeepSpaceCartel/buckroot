local common = import 'common.libsonnet';
local env = import 'env.libsonnet';

{
  adminHttpServers: [{
    listenAddresses: [':7982'],
    authenticationPolicy: { allow: {} },
  }],
  clientGrpcServers: [{
    listenAddresses: [':8982'],
    authenticationPolicy: { allow: {} },
    maximumReceivedMessageSizeBytes: 64 * 1024 * 1024,
  }],
  workerGrpcServers: [{
    listenAddresses: [':8983'],
    authenticationPolicy: { allow: {} },
  }],
  buildQueueStateGrpcServers: [{
    listenAddresses: [':8984'],
    authenticationPolicy: { allow: {} },
  }],
  contentAddressableStorage: common.blobstore.contentAddressableStorage,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  global: common.global,
  executeAuthorizer: { allow: {} },
  modifyDrainsAuthorizer: { allow: {} },
  killOperationsAuthorizer: { allow: {} },
  synchronizeAuthorizer: { allow: {} },
  actionRouter: {
    simple: {
      // Every action goes to the one worker pool. (`action: {}` routes by the platform in the
      // Action message, which Buck2's client leaves empty: the scheduler then reports
      // "No workers exist for ... platform {}". Multiple pools would need a client that
      // fills Action.platform.)
      platformKeyExtractor: {
        static: {
          properties: env.platformProperties,
        },
      },
      invocationKeyExtractors: [
        { correlatedInvocationsId: {} },
        { toolInvocationId: {} },
      ],
      initialSizeClassAnalyzer: {
        // One package build (toolchain overlay + make) can take several minutes.
        defaultExecutionTimeout: '1800s',
        maximumExecutionTimeout: '7200s',
      },
    },
  },
  platformQueueWithNoWorkersTimeout: env.noWorkersTimeout,
}
