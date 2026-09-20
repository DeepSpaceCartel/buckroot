// bb-portal: the successor of bb-browser. Browse the CAS and action cache (paste an action digest
// from `buck2 log what-ran`), and watch the scheduler (queues, workers, operations).
local common = import 'common.libsonnet';

{
  global: common.global,
  httpServers: [{
    listenAddresses: [':8081'],
    authenticationPolicy: { allow: {} },
  }],
  instanceNameAuthorizer: { allow: {} },
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  besServiceConfiguration: {
    grpcServers: [{
      listenAddresses: [':8082'],
      authenticationPolicy: { allow: {} },
      maximumReceivedMessageSizeBytes: 10 * 1024 * 1024,
    }],
    database: {
      postgres: { connectionString: 'postgresql://app:password@postgres:5432/app' },
      connectionPoolConfiguration: {
        maxOpenConnections: 10,
        maxIdleConnections: 10,
        connectionMaxLifetime: '120s',
        connectionMaxIdleTime: '30s',
      },
    },
    enableBepFileUpload: true,
    enableGraphqlPlayground: false,
    saveDataLevel: { basicAndTarget: {} },
    databaseCleanupConfiguration: {
      cleanupInterval: '60s',
      invocationMessageTimeout: '3600s',
      invocationRetention: '604800s',
    },
    minEventBatchDuration: '0.1s',
    buildKey: 'build_id',
  },
  contentAddressableStorage: common.blobstore.contentAddressableStorage,
  actionCache: common.blobstore.actionCache,
  schedulerServiceConfiguration: {
    buildQueueStateClient: { address: 'scheduler:8984' },
    killOperationsAuthorizer: { allow: {} },
    listOperationsPageSize: 500,
  },
  frontendServiceConfiguration: {
    frontendSource: { embedded: {} },
    frontendConfig: {
      companyName: 'Buck2 / Buildroot experiments',
      grpcBackendUrl: 'grpc://localhost:8082',
      featureFlags: {
        home: {},
        bes: {},
        browser: {},
        scheduler: {},
      },
    },
  },
}
