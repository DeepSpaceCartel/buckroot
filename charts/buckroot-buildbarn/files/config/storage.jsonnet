// One storage shard: CAS and action cache on block devices (files) with persistence.
// The largest blob the CAS can hold is ONE BLOCK: size / (old + current + new + spare blocks). 28 GiB / 22 = 1.27 GiB, enough for the
// 965 MB Google Fonts source archive of the Car Thing (16 GiB / 38 = 431 MiB rejected it: "Blob is 1011764312 bytes ... up to 452100096").
local common = import 'common.libsonnet';
local env = import 'env.libsonnet';

local store(dir, keyMapBytes, blocksBytes, newBlocks) = {
  'local': {
    keyLocationMapOnBlockDevice: { file: { path: dir + '/key_location_map', sizeBytes: keyMapBytes } },
    keyLocationMapMaximumGetAttempts: 16,
    keyLocationMapMaximumPutAttempts: 64,
    oldBlocks: 4,
    currentBlocks: 12,
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
    backend: store('/storage-cas', env.casKeyMapBytes, env.casSizeBytes, 3),
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
    findMissingAuthorizer: { allow: {} },
  },
  actionCache: {
    backend: store('/storage-ac', env.acKeyMapBytes, env.acSizeBytes, 1),
    getAuthorizer: { allow: {} },
    putAuthorizer: { allow: {} },
  },
}
