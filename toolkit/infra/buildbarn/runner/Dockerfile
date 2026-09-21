# The remote worker's tool baseline. Our wrapped actions run Buildroot's own make, which
# uses ambient host tools; the action key does not cover them, so pinning them in this
# image is what makes remote execution (and cache sharing between machines) sound.
# BASE selects the era of the baseline: a project pinned to an old Buildroot needs host tools of its time (Buildroot 2021.02's
# host-m4 does not build against glibc >= 2.34). ubuntu:24.04 is the default; ubuntu:20.04 (glibc 2.31, gcc 9) is the "legacy" one.
ARG BASE=ubuntu:24.04
FROM ${BASE}

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
      build-essential ca-certificates python3 perl rsync bc bison flex file which patch cpio \
      unzip wget curl bzip2 xz-utils gzip tar util-linux e2fsprogs libncurses-dev \
      findutils diffutils sed gawk pkg-config git xauth debianutils \
    && rm -rf /var/lib/apt/lists/*

# Same fixed PATH the actions use (see br2/pkg_action.py ENV).
ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
