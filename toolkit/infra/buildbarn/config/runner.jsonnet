// No diagnostics server here: in a Kubernetes pod the runner shares the worker's network namespace (and its diagnostics port).
{
  buildDirectoryPath: '/worker/build',
  grpcServers: [{
    listenPaths: ['/worker/runner'],
    authenticationPolicy: { allow: {} },
  }],
}
