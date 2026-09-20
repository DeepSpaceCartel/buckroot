# Buildbarn for the Buck2 experiment

```
cd infra/buildbarn
export BB_VOLUMES=/var/lib/buckroot-buildbarn
mkdir -p $BB_VOLUMES/{storage-ac,storage-cas}/persistent_state $BB_VOLUMES/worker/{build,cache/persistent_state} $BB_VOLUMES/{bb,runner-tmp} && chmod -R 0777 $BB_VOLUMES
docker compose up -d frontend storage   # phase 2: remote cache on localhost:8980
```

`.buckconfig` `[br2]` switches the cache on (`remote_cache`), lets this client write to it
(`cache_uploads`, leave off for untrusted builds) and `[buck2_re_client]` names the endpoint.
Config is trimmed from buildbarn/bb-deployments (docker-compose), one storage shard.

## Remote execution (phase 3)

```
docker compose up -d --build        # + scheduler, worker, runner (tool baseline image)
tools/buck2 build //:rootfs --config br2.remote_execution=true --config br2.local_execution=false
```

State lives in `/var/lib/buckroot-buildbarn` (override with `BB_VOLUMES`), outside the project on
purpose: worker build directories exhaust the inotify limit of Buck2's file watcher.

## Web UIs

| UI | URL (forward the port from the devcontainer) | What it shows |
|---|---|---|
| bb-scheduler | http://127.0.0.1:7982/ | platform queues, workers, running/queued operations |
| bb-portal | http://127.0.0.1:8081/ | browse the CAS and action cache; the scheduler view; build event data |

`bb-browser` was removed from Buildbarn's reference deployment; `bb-portal` (needs Postgres, in the compose file) replaces it.
To inspect an action: `buck2 log what-ran` prints its digest (`<hash>:<size>`); open the browser page of bb-portal and
paste it to see the command, environment, input tree and (for executed actions) the output tree, stdout and stderr.
