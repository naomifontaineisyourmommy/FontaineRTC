"""Host resource stats + MasterDNSVPN config (ported from OlcRTC-VPS).

Reads Linux /proc; on non-Linux dev hosts the readers degrade to zeros, which is
harmless because the node always runs on the Linux VPS alongside the binary.
"""

import re
from pathlib import Path

_MASTERDNS_BASE = Path("/opt/masterdnsvpn")
_cpu_prev: tuple[int, int] | None = None


def read_proc_io(pid: int) -> tuple[int, int]:
    """Return (rchar, wchar) for a pid; (0, 0) if unavailable."""
    try:
        d: dict[str, int] = {}
        with open(f"/proc/{pid}/io") as f:
            for line in f:
                k, _, v = line.partition(":")
                if v.strip():
                    d[k.strip()] = int(v.split()[0])
        return d.get("rchar", 0), d.get("wchar", 0)
    except Exception:
        return 0, 0


def server_stats() -> dict:
    global _cpu_prev
    stats = {"cpu_percent": 0.0, "mem_percent": 0.0, "mem_used_mb": 0, "mem_total_mb": 0}
    try:
        with open("/proc/stat") as f:
            parts = f.readline().split()
        vals = list(map(int, parts[1:]))
        idle = vals[3] + (vals[4] if len(vals) > 4 else 0)
        total = sum(vals)
        if _cpu_prev:
            d_idle, d_total = idle - _cpu_prev[0], total - _cpu_prev[1]
            if d_total > 0:
                stats["cpu_percent"] = round(100 * (1 - d_idle / d_total), 1)
        _cpu_prev = (idle, total)
    except Exception:
        pass
    try:
        mi: dict[str, int] = {}
        with open("/proc/meminfo") as f:
            for line in f:
                k, _, v = line.partition(":")
                if v.strip():
                    mi[k.strip()] = int(v.split()[0])
        total_kb = mi.get("MemTotal", 0)
        avail_kb = mi.get("MemAvailable", mi.get("MemFree", 0))
        used_kb = total_kb - avail_kb
        stats["mem_total_mb"] = total_kb // 1024
        stats["mem_used_mb"] = used_kb // 1024
        stats["mem_percent"] = round(100 * used_kb / total_kb, 1) if total_kb else 0
    except Exception:
        pass
    return stats


def masterdnsvpn_config() -> dict | None:
    """Return {'domain', 'key'} if MasterDNSVPN is installed, else None."""
    if not _MASTERDNS_BASE.exists():
        return None
    try:
        key = (_MASTERDNS_BASE / "encrypt_key.txt").read_text().strip()
        content = (_MASTERDNS_BASE / "server_config.toml").read_text()
        m = re.search(r'DOMAIN\s*=\s*\["(.+?)"\]', content)
        return {"domain": m.group(1) if m else None, "key": key}
    except Exception:
        return None
