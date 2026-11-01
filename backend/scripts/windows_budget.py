"""Windows Job memory/CPU budget. Supporting evidence, not Linux cgroup equivalence."""

import argparse
import ctypes as c
import json
import os
import subprocess
import sys
import time
from ctypes import wintypes as w
from pathlib import Path

import httpx

from scripts.resource_smoke import run


class BasicLimits(c.Structure):
    _fields_ = [
        ("process_time", c.c_int64),
        ("job_time", c.c_int64),
        ("flags", w.DWORD),
        ("min_ws", c.c_size_t),
        ("max_ws", c.c_size_t),
        ("active", w.DWORD),
        ("affinity", c.c_size_t),
        ("priority", w.DWORD),
        ("scheduling", w.DWORD),
    ]


class IO(c.Structure):
    _fields_ = [
        (name, c.c_uint64)
        for name in ["read", "write", "other", "read_bytes", "write_bytes", "other_bytes"]
    ]


class Extended(c.Structure):
    _fields_ = [
        ("basic", BasicLimits),
        ("io", IO),
        ("process_memory", c.c_size_t),
        ("job_memory", c.c_size_t),
        ("peak_process", c.c_size_t),
        ("peak_job", c.c_size_t),
    ]


class Accounting(c.Structure):
    _fields_ = [
        (name, c.c_int64) for name in ["user", "kernel", "period_user", "period_kernel"]
    ] + [(name, w.DWORD) for name in ["faults", "processes", "active", "terminated"]]


def main() -> None:
    if os.name != "nt":
        raise SystemExit("Use Docker --memory=512m --memory-swap=512m --cpus=0.1 on Linux")
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu-fraction", type=float, default=0)
    parser.add_argument("--report", type=Path, required=True)
    args = parser.parse_args()
    if "mustard_resource_test" not in os.environ.get("DATABASE_URL", ""):
        raise SystemExit("Use only the separate mustard_resource_test database")
    kernel = c.WinDLL("kernel32", use_last_error=True)
    kernel.CreateJobObjectW.restype = w.HANDLE
    kernel.AssignProcessToJobObject.argtypes = [w.HANDLE, w.HANDLE]
    kernel.SetInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD]
    kernel.QueryInformationJobObject.argtypes = [w.HANDLE, c.c_int, c.c_void_p, w.DWORD, c.c_void_p]
    kernel.TerminateJobObject.argtypes = [w.HANDLE, w.UINT]
    kernel.CloseHandle.argtypes = [w.HANDLE]
    job = kernel.CreateJobObjectW(None, None)
    limits = Extended()
    limits.basic.flags = 0x200 | 0x2000  # aggregate committed-memory cap; kill children on close
    limits.job_memory = 512 * 1024 * 1024
    if not kernel.SetInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits)):
        raise c.WinError(c.get_last_error())
    if args.cpu_fraction:
        rate = (w.DWORD * 2)(
            1 | 4, max(1, round(args.cpu_fraction / (os.cpu_count() or 1) * 10000))
        )
        if not kernel.SetInformationJobObject(job, 15, c.byref(rate), c.sizeof(rate)):
            raise c.WinError(c.get_last_error())
    env = {
        **os.environ,
        "PORT": "58001",
        "HOST": "127.0.0.1",
        "WEB_DIST": str(Path(__file__).resolve().parents[2] / "frontend/dist"),
        "BASE_URL": "http://127.0.0.1:58001",
        "ALLOWED_ORIGINS": '["http://127.0.0.1:58001"]',
        "ENVIRONMENT": "test",
        "DEV_AUTH": "true",
        "COOKIE_SECURE": "false",
        "MEDIA_CONCURRENCY": "1",
    }
    log = args.report.with_suffix(".log").open("w")
    child = subprocess.Popen(
        [sys.executable, "-m", "scripts.resource_server"],
        env=env,
        stdout=log,
        stderr=log,
        creationflags=0x00000004,  # CREATE_SUSPENDED (not exported by subprocess)
    )
    started = time.monotonic()
    results: dict[str, object] = {
        "platform": "Windows Job; not Render/Linux",
        "memory_limit_bytes": limits.job_memory,
        "requested_cpu_fraction": args.cpu_fraction,
        "fixtures": [],
    }
    try:
        if not kernel.AssignProcessToJobObject(job, w.HANDLE(int(child._handle))):
            child.kill()
            raise c.WinError(c.get_last_error())
        resume = c.WinDLL("ntdll").NtResumeProcess
        resume.argtypes = [w.HANDLE]
        if resume(w.HANDLE(int(child._handle))) != 0:
            raise RuntimeError("Could not resume constrained backend")
        for _ in range(240):
            if child.poll() is not None:
                raise RuntimeError("Backend exited under the resource limit")
            try:
                if httpx.get("http://127.0.0.1:58001/health", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            time.sleep(0.5)
        else:
            raise RuntimeError("Constrained backend startup timed out")
        results["fixtures"] = run(
            "http://127.0.0.1:58001",
            Path(__file__).resolve().parents[2] / ".tools/free-tier",
            results["fixtures"],
            ("720p", "portrait720p", "720p-high"),
        )
    except Exception as exc:
        results["failure"] = type(exc).__name__ + ": " + str(exc)
    finally:
        kernel.QueryInformationJobObject(job, 9, c.byref(limits), c.sizeof(limits), None)
        totals = Accounting()
        kernel.QueryInformationJobObject(job, 1, c.byref(totals), c.sizeof(totals), None)
        results.update(
            peak_committed_bytes=limits.peak_job,
            reported_peak_exceeds_configured_limit=limits.peak_job > limits.job_memory,
            aggregate_cpu_seconds=(totals.user + totals.kernel) / 10000000,
            elapsed_seconds=round(time.monotonic() - started, 2),
            backend_exit=child.poll(),
        )
        kernel.TerminateJobObject(job, 0)
        child.wait(timeout=10)
        kernel.CloseHandle(job)
        log.close()
        args.report.write_text(json.dumps(results, indent=2), encoding="utf-8")
        print(json.dumps(results), flush=True)
    fixtures = results["fixtures"]
    if (
        results.get("failure")
        or results.get("reported_peak_exceeds_configured_limit")
        or not fixtures
        or any(item.get("status") not in {200, 201} for item in fixtures)
    ):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
