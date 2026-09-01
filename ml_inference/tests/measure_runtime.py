from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def working_set_bytes() -> int | None:
    try:
        output = subprocess.check_output(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                f"(Get-Process -Id {os.getpid()}).WorkingSet64",
            ],
            text=True,
        )
        return int(output.strip())
    except Exception:
        pass
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
            _fields_ = [
                ("cb", wintypes.DWORD),
                ("PageFaultCount", wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(
            handle, ctypes.byref(counters), counters.cb
        )
        return int(counters.WorkingSetSize) if ok else None
    except Exception:
        return None


started = time.perf_counter()
from ml_inference.service import prediction_response  # noqa: E402

loaded = time.perf_counter()
payload = {
    "country_code": "CHN",
    "disaster_type": "Flood",
    "disaster_subtype": "Flood (General)",
    "event_date": "2023-07-15",
    "date_granularity": "day",
    "magnitude": 1000,
    "magnitude_scale": "Km2",
}
prediction_response(payload)
first_done = time.perf_counter()
warm_started = time.perf_counter()
prediction_response(payload)
warm_done = time.perf_counter()

print(
    json.dumps(
        {
            "pid": os.getpid(),
            "module_and_model_load_seconds": loaded - started,
            "first_prediction_seconds": first_done - loaded,
            "warm_prediction_seconds": warm_done - warm_started,
            "working_set_bytes": working_set_bytes(),
        },
        ensure_ascii=False,
        indent=2,
    )
)
