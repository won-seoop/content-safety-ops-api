import platform
import resource
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from threading import Lock


@dataclass
class RouteMetrics:
    count: int = 0
    error_count: int = 0
    total_latency_ms: float = 0
    recent_latencies_ms: deque[float] = field(default_factory=lambda: deque(maxlen=500))


class MetricsRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._started_at = time.time()
        self._routes: dict[str, RouteMetrics] = defaultdict(RouteMetrics)

    def record(self, method: str, path: str, status_code: int, latency_ms: float) -> None:
        route_key = f"{method} {path}"
        with self._lock:
            route = self._routes[route_key]
            route.count += 1
            route.total_latency_ms += latency_ms
            route.recent_latencies_ms.append(latency_ms)
            if status_code >= 500:
                route.error_count += 1

    def snapshot(self) -> dict:
        with self._lock:
            routes = []
            total_count = 0
            total_errors = 0
            all_latencies = []

            for route_key, route in self._routes.items():
                latencies = list(route.recent_latencies_ms)
                avg_latency = route.total_latency_ms / route.count if route.count else 0
                p95_latency = percentile(latencies, 95)
                total_count += route.count
                total_errors += route.error_count
                all_latencies.extend(latencies)
                routes.append(
                    {
                        "route": route_key,
                        "count": route.count,
                        "errorCount": route.error_count,
                        "avgLatencyMs": round(avg_latency, 2),
                        "p95LatencyMs": round(p95_latency, 2),
                    }
                )

            uptime_seconds = max(time.time() - self._started_at, 1)
            error_rate = total_errors / total_count if total_count else 0

            return {
                "uptimeSeconds": round(uptime_seconds, 2),
                "totalRequests": total_count,
                "errorCount": total_errors,
                "errorRate": round(error_rate, 4),
                "requestsPerSecond": round(total_count / uptime_seconds, 2),
                "avgLatencyMs": round(
                    sum(all_latencies) / len(all_latencies) if all_latencies else 0,
                    2,
                ),
                "p95LatencyMs": round(percentile(all_latencies, 95), 2),
                "memoryRssMb": round(get_current_rss_mb(), 2),
                "routes": sorted(routes, key=lambda item: item["count"], reverse=True),
            }


def percentile(values: list[float], percentile_value: int) -> float:
    if not values:
        return 0
    ordered = sorted(values)
    index = max(0, int(len(ordered) * percentile_value / 100) - 1)
    return ordered[index]


def get_current_rss_mb() -> float:
    try:
        with open("/proc/self/statm", encoding="utf-8") as statm:
            pages = int(statm.read().split()[1])
        return pages * resource.getpagesize() / 1024 / 1024
    except (FileNotFoundError, IndexError, ValueError):
        rss = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return rss / 1024 / 1024
        return rss / 1024


metrics_registry = MetricsRegistry()
