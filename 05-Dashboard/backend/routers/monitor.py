import os
import logging
import docker
import concurrent.futures
import threading
import time
from fastapi import APIRouter
from pydantic import BaseModel
from typing import List

logger = logging.getLogger("DashboardBackend.Monitor")

router = APIRouter(
    prefix="/api/v1/monitor",
    tags=["Monitor"],
)

class ContainerStats(BaseModel):
    name: str
    status: str
    cpu_percent: float
    memory_usage_mb: float
    memory_limit_mb: float
    memory_percent: float
    network_rx_mb: float
    network_tx_mb: float

class MonitorResponse(BaseModel):
    containers: List[ContainerStats]

# Global cache and lock for instant API responses
CONTAINER_STATS_CACHE: List[ContainerStats] = []
cache_lock = threading.Lock()

def calculate_cpu_percent(stats: dict) -> float:
    """Calculate CPU usage percentage from Docker container stats."""
    cpu_stats = stats.get("cpu_stats", {})
    precpu_stats = stats.get("precpu_stats", {})

    cpu_usage = cpu_stats.get("cpu_usage", {})
    precpu_usage = precpu_stats.get("cpu_usage", {})
    
    cpu_delta = cpu_usage.get("total_usage", 0) - precpu_usage.get("total_usage", 0)
    system_delta = cpu_stats.get("system_cpu_usage", 0) - precpu_stats.get("system_cpu_usage", 0)
    
    online_cpus = cpu_stats.get("online_cpus", len(cpu_usage.get("percpu_usage", [])) or 1)

    if system_delta > 0.0 and cpu_delta > 0.0:
        return round((cpu_delta / system_delta) * online_cpus * 100.0, 2)
    return 0.0

def calculate_memory_stats(stats: dict) -> tuple[float, float, float]:
    """Calculate Memory usage, limit (MB) and percentage from Docker container stats."""
    memory_stats = stats.get("memory_stats", {})
    
    mem_usage = memory_stats.get("usage", 0)
    stats_detail = memory_stats.get("stats", {})
    cache = stats_detail.get("cache", 0)
    active_memory = mem_usage - cache
    
    limit = memory_stats.get("limit", 1)
    
    usage_mb = round(active_memory / (1024 * 1024), 2)
    limit_mb = round(limit / (1024 * 1024), 2)
    
    percent = round((active_memory / limit) * 100.0, 2) if limit > 0 else 0.0
    return usage_mb, limit_mb, percent

def calculate_network_stats(stats: dict) -> tuple[float, float]:
    """Calculate Network RX and TX (MB) from Docker container stats."""
    networks = stats.get("networks", {})
    rx_bytes = sum(iface.get("rx_bytes", 0) for iface in networks.values())
    tx_bytes = sum(iface.get("tx_bytes", 0) for iface in networks.values())
    
    rx_mb = round(rx_bytes / (1024 * 1024), 2)
    tx_mb = round(tx_bytes / (1024 * 1024), 2)
    return rx_mb, tx_mb

def fetch_single_container_stats(container) -> ContainerStats:
    """Fetch and calculate stats for a single container."""
    cpu_percent = 0.0
    memory_usage_mb = 0.0
    memory_limit_mb = 0.0
    memory_percent = 0.0
    network_rx_mb = 0.0
    network_tx_mb = 0.0

    if container.status == "running":
        try:
            # Query stats synchronously (non-streaming)
            stats = container.stats(stream=False)
            cpu_percent = calculate_cpu_percent(stats)
            memory_usage_mb, memory_limit_mb, memory_percent = calculate_memory_stats(stats)
            network_rx_mb, network_tx_mb = calculate_network_stats(stats)
        except Exception as e:
            logger.warning(f"Failed to retrieve stats for container {container.name}: {e}")

    return ContainerStats(
        name=container.name,
        status=container.status,
        cpu_percent=cpu_percent,
        memory_usage_mb=memory_usage_mb,
        memory_limit_mb=memory_limit_mb,
        memory_percent=memory_percent,
        network_rx_mb=network_rx_mb,
        network_tx_mb=network_tx_mb
    )

def bg_monitor_worker():
    """Background worker that updates container stats cache every 3 seconds."""
    logger.info("Starting background container monitor worker")
    
    while True:
        try:
            try:
                client = docker.from_env()
            except Exception as e:
                logger.error(f"Failed to connect to Docker daemon in background: {e}")
                time.sleep(5)
                continue

            # Read allowed container names from .env dynamically
            containers_env = os.getenv("CONTAINERS", "").strip()
            allowed_names = {
                name.strip()
                for name in containers_env.split(",")
                if name.strip()
            }

            try:
                containers = client.containers.list(all=True)
            except Exception as e:
                logger.error(f"Failed to list containers in background: {e}")
                time.sleep(5)
                continue

            filtered_containers = [
                c for c in containers
                if not allowed_names or c.name in allowed_names
            ]

            temp_stats = []
            # Query stats concurrently
            with concurrent.futures.ThreadPoolExecutor(max_workers=len(filtered_containers) or 1) as executor:
                futures = {
                    executor.submit(fetch_single_container_stats, c): c.name
                    for c in filtered_containers
                }
                
                try:
                    for future in concurrent.futures.as_completed(futures, timeout=4.0):
                        try:
                            temp_stats.append(future.result())
                        except Exception as e:
                            name = futures[future]
                            logger.error(f"Error fetching stats for {name}: {e}")
                            temp_stats.append(ContainerStats(
                                name=name,
                                status="unknown",
                                cpu_percent=0.0,
                                memory_usage_mb=0.0,
                                memory_limit_mb=0.0,
                                memory_percent=0.0,
                                network_rx_mb=0.0,
                                network_tx_mb=0.0
                            ))
                except concurrent.futures.TimeoutError:
                    completed_names = {res.name for res in temp_stats}
                    for future, name in futures.items():
                        if name not in completed_names:
                            temp_stats.append(ContainerStats(
                                name=name,
                                status="unknown",
                                cpu_percent=0.0,
                                memory_usage_mb=0.0,
                                memory_limit_mb=0.0,
                                memory_percent=0.0,
                                network_rx_mb=0.0,
                                network_tx_mb=0.0
                            ))

            # Sort and update cache
            temp_stats.sort(key=lambda x: x.name)
            with cache_lock:
                global CONTAINER_STATS_CACHE
                CONTAINER_STATS_CACHE = temp_stats

        except Exception as e:
            logger.error(f"Unexpected error in background monitor worker: {e}")

        time.sleep(10)

# Start background monitor thread immediately
monitor_thread = threading.Thread(target=bg_monitor_worker, daemon=True)
monitor_thread.start()

@router.get("/containers", response_model=MonitorResponse)
def get_containers_monitor():
    """Fetch cached real-time CPU, RAM, and Network usage for Docker containers instantly."""
    with cache_lock:
        # If cache is not populated yet, return an empty list or try to return a quick empty state
        return MonitorResponse(containers=list(CONTAINER_STATS_CACHE))
