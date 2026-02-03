import inspect
from typing import Dict, Optional

import httpx


def get_httpx_client(
    timeout: float = 10.0,
    http2: bool = True,
    proxies: Optional[str] = None,
    headers: Optional[Dict[str, str]] = None
) -> httpx.Client:
    client_kwargs: Dict[str, object] = {
        "timeout": timeout,
        "http2": http2,
        "headers": headers,
    }
    if proxies:
        client_params = inspect.signature(httpx.Client).parameters
        if "proxies" in client_params:
            client_kwargs["proxies"] = proxies
    return httpx.Client(**client_kwargs)
