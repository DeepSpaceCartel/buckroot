# Execution platform with switchable remote features (the prelude's default platform
# hard-codes remote_enabled = False and no cache). Toggle from .buckconfig / --config:
#
#   [br2]
#     remote_cache = true       # look actions up in / upload results to the REAPI cache
#     cache_uploads = true      # trust boundary: only trusted builds should upload
#     remote_execution = false  # phase 3: run actions on Buildbarn workers
#     local_execution = true    # false = never run locally (proves everything runs remotely)
#
# The [buck2_re_client] section names the endpoint.

load("@prelude//cfg/exec_platform:marker.bzl", "get_exec_platform_marker")

def _impl(ctx: AnalysisContext) -> list[Provider]:
    constraints = dict()
    constraints.update(ctx.attrs.cpu_configuration[ConfigurationInfo].constraints)
    constraints.update(ctx.attrs.os_configuration[ConfigurationInfo].constraints)
    cfg = ConfigurationInfo(constraints = constraints, values = {})

    name = ctx.label.raw_target()
    platform = ExecutionPlatformInfo(
        label = name,
        configuration = cfg,
        executor_config = CommandExecutorConfig(
            local_enabled = ctx.attrs.local_execution,
            remote_enabled = ctx.attrs.remote_execution,
            remote_cache_enabled = ctx.attrs.remote_cache,
            allow_cache_uploads = ctx.attrs.cache_uploads,
            remote_execution_properties = ctx.attrs.remote_execution_properties,
            remote_execution_use_case = "br2",
            use_windows_path_separators = False,
        ),
    )
    return [
        DefaultInfo(),
        platform,
        PlatformInfo(label = str(name), configuration = cfg),
        ExecutionPlatformRegistrationInfo(
            platforms = [platform],
            exec_marker_constraint = get_exec_platform_marker(),
        ),
    ]

br2_execution_platform = rule(
    impl = _impl,
    attrs = {
        "cache_uploads": attrs.bool(default = False),
        "cpu_configuration": attrs.dep(providers = [ConfigurationInfo]),
        "os_configuration": attrs.dep(providers = [ConfigurationInfo]),
        "local_execution": attrs.bool(default = True),
        "remote_cache": attrs.bool(default = False),
        "remote_execution": attrs.bool(default = False),
        "remote_execution_properties": attrs.dict(key = attrs.string(), value = attrs.string(), default = {}),
    },
)
