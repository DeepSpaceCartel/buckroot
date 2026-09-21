#!/bin/bash
# cmake 3.15.5's Source/cmWorkerPool.h uses std::int64_t but includes only the C header <stdint.h>, which does not declare it in namespace
# std; it compiled where <memory> happened to pull in <cstdint> and failed in the Buck2 action (same compiler and flags, gcc 9.4,
# -std=gnu++17: the cause of the difference was not pinned down). Buildroot applies package/cmake/*.patch to the cmake source, so the
# fix is one more patch file of that kind: it adds the missing include and changes nothing in any output.
set -euo pipefail
cat > package/cmake/0002-cmworkerpool-include-cstdint.patch <<'PATCH'
cmWorkerPool.h uses std::int64_t and includes only <stdint.h>: include <cstdint>.

--- a/Source/cmWorkerPool.h
+++ b/Source/cmWorkerPool.h
@@ -8,6 +8,7 @@
 #include "cmAlgorithms.h" // IWYU pragma: keep
 
 #include <memory> // IWYU pragma: keep
+#include <cstdint>
 #include <stdint.h>
 #include <string>
 #include <utility>
PATCH
