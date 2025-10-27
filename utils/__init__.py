import os
import logging
from hashlib import sha256
from urllib.parse import urlparse

def get_logger(name, filename=None):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    if not os.path.exists("Logs"):
        os.makedirs("Logs")
    fh = logging.FileHandler(f"Logs/{filename if filename else name}.log")
    fh.setLevel(logging.DEBUG)
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter(
       "%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    fh.setFormatter(formatter)
    ch.setFormatter(formatter)
    # add the handlers to the logger
    logger.addHandler(fh)
    logger.addHandler(ch)
    return logger


def get_urlhash(url):
    parsed = urlparse(url)
    # everything other than scheme.
    return sha256(
        f"{parsed.netloc}/{parsed.path}/{parsed.params}/"
        f"{parsed.query}/{parsed.fragment}".encode("utf-8")).hexdigest()

def normalize(url):
    if url.endswith("/"):
        return url.rstrip("/")
    return url

# used for loop-detection
def get_subdomain(url):
        '''returns up until the subdomain of a url assuming it has been normalized
            example: get_subdomain(self, "https://ics.uci.edu/~eppstein/pix/ham/Sara2.html) will return
            "https://ics.uci/edu/~eppstein/"
        '''
        parsed = urlparse(url)

        scheme = parsed.scheme  # https
        netloc = parsed.netloc  # ics.uci.edu
        path = parsed.path  # /~eppstein/pix/ham/Sara2.html

        if path.startswith('/') and len(path) > 1: # checks if there is even a subdomain to begin with
            # if path = /~eppstein/pix/ham/Sara2.html, new path = /~eppstein/
            path = "/" + path[1:].split("/")[0]+"/"

        return f"{scheme}://{netloc}{path}"


