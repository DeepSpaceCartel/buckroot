// Hardlinking worker: inputs are downloaded into a local cache and hardlinked into a
// per-action build directory. The runner (a separate, privileged container with the tool
// baseline) executes the command there.
local common = import 'common.libsonnet';
local env = import 'env.libsonnet';

{
  blobstore: common.blobstore,
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  scheduler: { address: env.schedulerWorkerAddress },
  global: common.global,
  buildDirectories: [{
    native: {
      buildDirectoryPath: '/worker/build',
      cacheDirectoryPath: '/worker/cache',
      maximumCacheFileCount: env.workerCacheFiles,
      maximumCacheSizeBytes: env.workerCacheBytes,
      cacheReplacementPolicy: 'LEAST_RECENTLY_USED',
    },
    runners: [{
      endpoint: { address: 'unix:///worker/runner' },
      concurrency: env.workerConcurrency,
      instanceNamePrefix: '',
      platform: {
        properties: env.platformProperties,
      },
      workerId: { pool: env.workerPool } + import 'gen/id.libsonnet',
    }],
  }],
  inputDownloadConcurrency: 10,
  outputUploadConcurrency: 11,
  directoryCache: {
    maximumCount: 10000,
    maximumSizeBytes: 16 * 1024 * 1024,
    cacheReplacementPolicy: 'LEAST_RECENTLY_USED',
  },
}
