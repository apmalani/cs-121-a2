import requests
import cbor
import time

from utils.response import Response

def download(url, config, logger=None):
    host, port = config.cache_server
    timeout = 90
    try:
        resp = requests.get(
            f"http://{host}:{port}/",
            params=[("q", f"{url}"), ("u", f"{config.user_agent}")],
            timeout=timeout)
        try:
            if resp and resp.content:
                return Response(cbor.loads(resp.content))
        except (EOFError, ValueError) as e:
            pass
        if logger:
            logger.error(f"Spacetime Response error {resp} with url {url}.")
        return Response({
            "error": f"Spacetime Response error {resp} with url {url}.",
            "status": resp.status_code,
            "url": url})
    except requests.Timeout:
        if logger:
            logger.error(f"Timeout after {timeout}s for {url}.")
        return Response({
            "error": f"Request timeout after {timeout}s.",
            "status": 504,
            "url": url})
    except requests.RequestException as e:
        if logger:
            logger.error(f"Request error for {url}: {e}.")
        return Response({
            "error": f"Request error: {str(e)}",
            "status": 503,
            "url": url})
