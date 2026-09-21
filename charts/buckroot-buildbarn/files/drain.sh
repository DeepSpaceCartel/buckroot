# preStop hook of every container of a worker pod (run as: /tools/busybox sh /drain/drain.sh).
#
# Deleting a worker pod used to mean "sleep 60, then stop": for those 60 seconds the pod stayed registered with the
# scheduler and was still handed new actions, and an action that was running when the pod stopped failed the client with
# an EOF. So: first tell the scheduler to stop assigning to this worker (a drain, the admin UI's "add_drain" form), then
# wait until the scheduler no longer lists the worker as executing, then return; only then does the container get SIGTERM.
# Every container of the pod runs the same script, so none stops before the last action ends. Drains are idempotent.
#
# Environment (set by the chart): POD_NAME, ADMIN (scheduler admin URL), QUEUE and EXECUTING (URL-encoded JSON of the
# scheduler's platform queue and of its "executing workers" filter), DRAIN_TIMEOUT and FALLBACK (seconds).
B=/tools/busybox
now() { $B date +%s; }
reachable() { $B wget -q -T 5 -O /dev/null "${ADMIN}/"; }
end=$(( $(now) + DRAIN_TIMEOUT ))

# The admin pages answer 404 when the scheduler has no worker for the queue (none registered, or already expired): then
# nothing can be assigned to this pod and there is nothing to wait for.
if ! $B wget -q -T 5 -O /dev/null \
    --post-data "size_class_queue_name=${QUEUE}&worker_id_pattern=%7B%22slot%22%3A%22${POD_NAME}%22%7D" "${ADMIN}/add_drain"; then
  if reachable; then exit 0; fi
  # scheduler unreachable: the previous behaviour (a fixed delay) is the best that is left
  echo "drain: cannot reach ${ADMIN}; waiting ${FALLBACK}s instead" >&2
  $B sleep "$FALLBACK"
  exit 0
fi

while [ "$(now)" -lt "$end" ]; do
  if page=$($B wget -q -T 5 -O - "${ADMIN}/workers?filter=${EXECUTING}"); then
    echo "$page" | $B grep -q "$POD_NAME" || exit 0        # not listed as executing: idle, and drained
  elif reachable; then
    exit 0
  fi
  $B sleep 2
done
echo "drain: ${POD_NAME} still executing after ${DRAIN_TIMEOUT}s; giving up" >&2
