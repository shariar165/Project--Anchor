"""Host process metrics for the super-admin System dashboards.

Thin wrapper around psutil. Every value is best-effort: if psutil is missing or a
probe raises (e.g. a sandboxed container with no /proc), the field degrades to
None rather than 500-ing the endpoint that called it.
"""
from __future__ import annotations

import time

try:
    import psutil  # type: ignore
except Exception:  # pragma: no cover - psutil should be installed, but never hard-fail
    psutil = None  # type: ignore

# Process start time, captured at import. psutil.Process().create_time() is more
# accurate but this is a robust fallback and avoids a per-call syscall.
_BOOT = time.time()


def _safe(fn, default=None):
    try:
        return fn()
    except Exception:
        return default


def host_metrics() -> dict:
    """Return a flat dict of host/process metrics. Missing values are None.

    Keys: available (bool), cpu_percent, mem_used_mb, mem_total_mb, mem_percent,
    process_uptime_s, process_rss_mb, disk_percent.
    """
    if psutil is None:
        return {
            "available": False,
            "cpu_percent": None,
            "mem_used_mb": None,
            "mem_total_mb": None,
            "mem_percent": None,
            "process_uptime_s": int(time.time() - _BOOT),
            "process_rss_mb": None,
            "disk_percent": None,
        }

    # interval=None returns the % since the last call (non-blocking); good enough
    # for a dashboard polled every few seconds.
    cpu = _safe(lambda: psutil.cpu_percent(interval=None))
    vm = _safe(lambda: psutil.virtual_memory())
    disk = _safe(lambda: psutil.disk_usage("/"))

    proc = _safe(lambda: psutil.Process())
    uptime = None
    rss_mb = None
    if proc is not None:
        ctime = _safe(lambda: proc.create_time())
        if ctime is not None:
            uptime = int(time.time() - ctime)
        rss = _safe(lambda: proc.memory_info().rss)
        if rss is not None:
            rss_mb = round(rss / (1024 * 1024), 1)
    if uptime is None:
        uptime = int(time.time() - _BOOT)

    return {
        "available": True,
        "cpu_percent": round(cpu, 1) if cpu is not None else None,
        "mem_used_mb": round(vm.used / (1024 * 1024)) if vm is not None else None,
        "mem_total_mb": round(vm.total / (1024 * 1024)) if vm is not None else None,
        "mem_percent": round(vm.percent, 1) if vm is not None else None,
        "process_uptime_s": uptime,
        "process_rss_mb": rss_mb,
        "disk_percent": round(disk.percent, 1) if disk is not None else None,
    }
