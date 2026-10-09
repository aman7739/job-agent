"""Keepalive script for Render Web Service.

Sends periodic health ping requests to prevent Render free-tier instances
from spinning down due to the 15-minute inactivity idle timeout.
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
import time
from datetime import datetime, timezone
from typing import Optional

import httpx

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("keepalive")

DEFAULT_TIMEOUT = 30.0  # Allow up to 30s in case container is waking up


def ping_health_endpoint(target_url: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    """Send a lightweight HTTP GET request to the /health endpoint.

    Args:
        target_url: Base URL or full URL to /health.
        timeout: Request timeout in seconds.

    Returns:
        True if the service responded with HTTP 200, False otherwise.
    """
    clean_url = target_url.strip().rstrip("/")
    if not clean_url.endswith("/health"):
        health_url = f"{clean_url}/health"
    else:
        health_url = clean_url

    headers = {
        "User-Agent": "JobDigestAgent-KeepAlive/1.0 (+https://github.com/aman7739/job-agent)",
        "Accept": "application/json",
    }

    start = time.perf_counter()
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            resp = client.get(health_url, headers=headers)
            elapsed_ms = (time.perf_counter() - start) * 1000.0

            if resp.status_code == 200:
                data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                uptime = data.get("uptime_seconds", "N/A")
                db_status = data.get("database", "N/A")
                logger.info(
                    "PONG 200 OK | Latency: %.1fms | Uptime: %ss | DB: %s | Target: %s",
                    elapsed_ms,
                    uptime,
                    db_status,
                    health_url,
                )
                return True
            else:
                logger.warning(
                    "UNHEALTHY HTTP %d | Latency: %.1fms | Response: %s",
                    resp.status_code,
                    elapsed_ms,
                    resp.text[:200],
                )
                return False

    except httpx.ConnectTimeout:
        logger.error("Connection timed out after %.1fs (Render container may be booting)", timeout)
        return False
    except httpx.HTTPError as exc:
        logger.error("HTTP request error pinging %s: %s", health_url, exc)
        return False
    except Exception as exc:
        logger.error("Unexpected error during keepalive ping: %s", exc)
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Render Free-Tier Keepalive Ping Tool",
    )
    parser.add_argument(
        "--url",
        "-u",
        type=str,
        default=os.getenv("RENDER_APP_URL"),
        help="Target base URL of Render web service (or set RENDER_APP_URL)",
    )
    parser.add_argument(
        "--interval",
        "-i",
        type=int,
        default=600,
        help="Interval in seconds for loop mode (default: 600s / 10 mins)",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run continuously in a loop at the specified interval",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help="HTTP request timeout in seconds (default: 30s)",
    )

    args = parser.parse_args()

    if not args.url:
        logger.error("No target URL specified. Set RENDER_APP_URL environment variable or pass --url <URL>.")
        return 1

    if args.loop:
        logger.info("Starting keepalive loop targeting %s every %ds...", args.url, args.interval)
        try:
            while True:
                ping_health_endpoint(args.url, timeout=args.timeout)
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Keepalive loop terminated by user.")
            return 0
    else:
        success = ping_health_endpoint(args.url, timeout=args.timeout)
        return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
