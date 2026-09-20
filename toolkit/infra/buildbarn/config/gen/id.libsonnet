// The worker's slot in its ID. Docker Compose: one worker, slot '0'. Kubernetes: an init container overwrites this
// file with the pod name, so every pod has a unique worker ID (the scheduler tells workers apart by it).
{ slot: '0' }
