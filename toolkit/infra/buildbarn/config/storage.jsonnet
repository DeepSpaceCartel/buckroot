// One storage shard: CAS and action cache on block devices (files) with persistence.
local common = import 'common.libsonnet';

local store(dir, keyMapBytes, blocksBytes, newBlocks) = {
  'local': {
    keyLocationMapOnBlockDevice: { file: { path: dir + '/key_location_map', sizeBytes: keyMapBytes } },
    keyLocationMapMaximumGetAttempts: 16,
    keyLocationMapMaximumPutAttempts: 64,
    oldBlocks: 8,
    currentBlocks: 24,
    newBlocks: newBlocks,
    blocksOnBlockDevice: {
      source: { file: { path: dir + '/blocks', sizeBytes: blocksBytes } },
      spareBlocks: 3,
    },
    persistent: {
      stateDirectoryPath: dir + '/persistent_state',
      minimumEpochInterval: '300s',
    },
  },
};

{
  grpcServers: [{
    listenAddresses: [':8981'],
    authenticationPolicy: { allow: {} },
    // Buck2 uploads input-root Directory messages and blob batches larger than gRPC's 4 MiB default.
    maximumReceivedMessageSizeBytes: 64 * 1024 * 1024,
  }],
  maximumMessageSizeBytes: common.maximumMessageSizeBytes,
  global: common.global,
  contentAddressableStorage: {
    backend: store('/storage-cas', 400 * 1024 * 1024, 16 * 1024 * 1024 * 1024, 3),
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
    findMissingAuthorizer: { allow: {} },
  },
  actionCache: {
    backend: store('/storage-ac', 16 * 1024 * 1024, 256 * 1024 * 1024, 1),
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
  },
}
