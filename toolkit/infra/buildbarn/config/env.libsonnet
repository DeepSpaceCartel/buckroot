// Every tunable of the Buildbarn stack in one place. The defaults are the Docker Compose stack; the Helm chart
// (charts/buckroot-buildbarn) replaces this file with values from values.yaml, and nothing else changes.
{
  // Service addresses.
  storageAddress: 'storage:8981',
  schedulerWorkerAddress: 'scheduler:8983',  // worker -> scheduler
  schedulerStateAddress: 'scheduler:8984',   // portal -> scheduler
  // Frontend routing: instance-name prefix -> the scheduler (client address) that queues that instance's actions.
  // '' is the default. Several entries give several worker pools, chosen by the client's `instance_name`.
  schedulers: { '': 'scheduler:8982' },

  // How long the scheduler keeps an action queued when no worker exists for its platform. With workers scaled to
  // zero it must exceed a node's cold start.
  noWorkersTimeout: '120s',

  // Storage. One blob has to fit in ONE block: block size = sizeBytes / (old + current + new + spare blocks).
  casSizeBytes: 28 * 1024 * 1024 * 1024,
  casKeyMapBytes: 400 * 1024 * 1024,
  acSizeBytes: 256 * 1024 * 1024,
  acKeyMapBytes: 16 * 1024 * 1024,

  // Worker.
  workerPool: 'buckroot',
  workerConcurrency: 1,
  workerCacheBytes: 8 * 1024 * 1024 * 1024,
  workerCacheFiles: 100000,
  platformProperties: [
    { name: 'OSFamily', value: 'linux' },
    { name: 'container-image', value: 'docker://buckroot-worker' },
  ],

  // Diagnostics (Prometheus metrics, pprof).
  diagnosticsAddress: ':80',

  // Portal.
  postgresConnection: 'postgresql://app:password@postgres:5432/app',
  portalGrpcBackendUrl: 'grpc://localhost:8082',
}
