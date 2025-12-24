import time
from dataclasses import dataclass
from typing import Optional

import requests
from requests.adapters import HTTPAdapter

try:
    from urllib3.util.retry import Retry
except Exception:  # pragma: no cover
    Retry = None


@dataclass
class HttpPolicy:
    timeout_seconds: float = 10.0
    retries: int = 3
    backoff_seconds: tuple[float, float, float] = (0.5, 2.0, 5.0)


class PoliteHttpClient:
    def __init__(self, policy: Optional[HttpPolicy] = None, user_agent: str = "OpportunityRadar/1.0"):
        self.policy = policy or HttpPolicy()
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

        if Retry is not None:
            retry = Retry(
                total=self.policy.retries,
                connect=self.policy.retries,
                read=self.policy.retries,
                status=self.policy.retries,
                backoff_factor=0.5,
                status_forcelist=(429, 500, 502, 503, 504),
                allowed_methods=("GET", "HEAD"),
                raise_on_status=False,
            )
            adapter = HTTPAdapter(max_retries=retry)
            self.session.mount("http://", adapter)
            self.session.mount("https://", adapter)

        self._last_request_at_by_source: dict[str, float] = {}

    def get(self, url: str, source_id: str, min_interval_seconds: float = 0.0) -> requests.Response:
        last = self._last_request_at_by_source.get(source_id)
        if last is not None and min_interval_seconds > 0:
            sleep_for = (last + min_interval_seconds) - time.time()
            if sleep_for > 0:
                time.sleep(sleep_for)

        resp = self.session.get(url, timeout=self.policy.timeout_seconds)

        # If urllib3 Retry isn't available, do a tiny manual backoff loop.
        if Retry is None and resp.status_code in (429, 500, 502, 503, 504):
            for backoff in self.policy.backoff_seconds:
                time.sleep(backoff)
                resp = self.session.get(url, timeout=self.policy.timeout_seconds)
                if resp.status_code < 400:
                    break

        self._last_request_at_by_source[source_id] = time.time()
        resp.raise_for_status()
        return resp
