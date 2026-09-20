#!/usr/bin/env python3
"""Tier 0 functional test: boot the Buildroot image under QEMU and run hello.

Boots output/images/{Image,rootfs.ext4} with the host QEMU that Buildroot built,
logs in on the serial console and asserts that:
  - the guest really is aarch64,
  - /usr/bin/hello prints its greeting,
  - /usr/bin/hello exits 0.

The disk is attached with snapshot=on, so rootfs.ext4 is never modified.
Stdlib only. Exit status: 0 pass, 1 test failure, 2 missing build artifacts.

Env: TIER0_BOOT_TIMEOUT (seconds to reach the login prompt, default 300).
"""
import os
import queue
import re
import subprocess
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent
OUT = HERE / "buildroot-src" / "output"
QEMU = OUT / "host" / "bin" / "qemu-system-aarch64"
KERNEL = OUT / "images" / "Image"
# TIER0_ROOTFS: boot a different rootfs (e.g. the one Buck2 built) with the same kernel.
ROOTFS = Path(os.environ.get("TIER0_ROOTFS", OUT / "images" / "rootfs.ext4")).resolve()
SERIAL_LOG = OUT / "test-tier0.serial.log"

# Keep in sync with common/hello/hello.c.
GREETING = "hello from buckroot helloworld"

BOOT_TIMEOUT = float(os.environ.get("TIER0_BOOT_TIMEOUT", "300"))
CMD_TIMEOUT = 60.0
PROMPT = r"^# $"  # matched with re.MULTILINE (see Console.expect)


class TestFailure(Exception):
    pass


class Console:
    """Minimal expect-style wrapper around QEMU's serial console (stdin/stdout)."""

    def __init__(self, argv):
        self.proc = subprocess.Popen(
            argv, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, bufsize=0)
        self.buf = ""
        self.transcript = ""
        self.chunks = queue.Queue()
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self):
        fd = self.proc.stdout.fileno()
        while True:
            data = os.read(fd, 4096)
            self.chunks.put(data or None)
            if not data:
                return

    def send(self, text):
        self.proc.stdin.write(text.encode())
        self.proc.stdin.flush()

    def expect(self, pattern, timeout, what):
        """Wait for regex `pattern`; return (text before match, match)."""
        deadline = time.monotonic() + timeout
        while True:
            m = re.search(pattern, self.buf, re.MULTILINE)
            if m:
                before = self.buf[:m.start()]
                self.buf = self.buf[m.end():]
                return before, m
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TestFailure(f"timed out after {timeout:.0f}s waiting for {what}")
            try:
                chunk = self.chunks.get(timeout=remaining)
            except queue.Empty:
                continue
            if chunk is None:
                raise TestFailure(f"QEMU exited while waiting for {what}")
            text = chunk.decode(errors="replace").replace("\r", "")
            self.buf += text
            self.transcript += text

    def close(self):
        if self.proc.poll() is None:
            self.proc.kill()
        self.proc.wait()


def qemu_argv():
    return [
        str(QEMU), "-M", "virt", "-cpu", "cortex-a53", "-smp", "1", "-nographic",
        "-kernel", str(KERNEL),
        "-append", "rootwait root=/dev/vda console=ttyAMA0",
        "-netdev", "user,id=eth0", "-device", "virtio-net-device,netdev=eth0",
        "-drive", f"file={ROOTFS},if=none,format=raw,id=hd0,snapshot=on",
        "-device", "virtio-blk-device,drive=hd0",
    ]


def run_test(con):
    step = 0

    def ok(msg):
        nonlocal step
        step += 1
        print(f"  ok {step}: {msg}", flush=True)

    con.expect(r"login: ", BOOT_TIMEOUT, "login prompt (boot)")
    ok("guest booted to login prompt")

    con.send("root\n")
    _, m = con.expect(r"Password: |" + PROMPT, CMD_TIMEOUT, "shell prompt after login")
    if m.group(0).startswith("Password"):
        con.send("\n")
        con.expect(PROMPT, CMD_TIMEOUT, "shell prompt after empty password")
    ok("logged in as root")

    # Markers use $(...) / $? in the command so the tty's echo of what we typed
    # can never satisfy the regex; only the command's real output can.
    con.send("echo ARCH=$(uname -m)\n")
    _, m = con.expect(r"ARCH=(\w+)\n", CMD_TIMEOUT, "uname output")   # \n: the whole line, not a partial read
    if m.group(1) != "aarch64":
        raise TestFailure(f"guest arch is {m.group(1)!r}, expected 'aarch64'")
    ok("guest arch is aarch64 (not the x86_64 host)")

    con.send('hello; echo "RC=$?"\n')
    output, m = con.expect(r"RC=(\d+)\n", CMD_TIMEOUT, "hello to finish")
    if GREETING not in output:
        raise TestFailure(f"greeting {GREETING!r} not in hello output:\n{output!r}")
    ok(f"hello printed {GREETING!r}")
    if m.group(1) != "0":
        raise TestFailure(f"hello exited with status {m.group(1)}, expected 0")
    ok("hello exited 0")

    con.send("poweroff\n")


def main():
    missing = [p for p in (QEMU, KERNEL, ROOTFS) if not p.exists()]
    if missing:
        print("missing build artifacts (run scripts/build-tier0.sh first):", file=sys.stderr)
        for p in missing:
            print(f"  {p}", file=sys.stderr)
        return 2

    print(f"booting {ROOTFS.name} under qemu-system-aarch64 (TCG, no KVM; boot may take a minute)")
    con = Console(qemu_argv())
    try:
        run_test(con)
        try:
            con.proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            pass  # test already passed; close() kills the stragglers
        print("PASS")
        return 0
    except TestFailure as e:
        print(f"FAIL: {e}", file=sys.stderr)
        tail = "\n".join((con.transcript + con.buf).splitlines()[-40:])
        print(f"--- last serial output (full log: {SERIAL_LOG}) ---\n{tail}", file=sys.stderr)
        return 1
    finally:
        con.close()
        SERIAL_LOG.write_text(con.transcript)


if __name__ == "__main__":
    sys.exit(main())
