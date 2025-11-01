import os
import logging
import re
from bs4 import BeautifulSoup
from hashlib import sha256
from urllib.parse import urlparse

_WORD_RE = re.compile(r'\b[a-zA-Z]+\b')

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
    return sha256(
        f"{parsed.netloc}/{parsed.path}/{parsed.params}/"
        f"{parsed.query}/{parsed.fragment}".encode("utf-8")).hexdigest()

def normalize(url):
    try:
        parsed = urlparse(url)
        
        if '#' in url:
            url = url.split('#')[0]
            parsed = urlparse(url)
        
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path
        query = parsed.query
        
        if netloc.startswith('www.'):
            netloc = netloc[4:]
        
        if path.endswith('/') and path != '/':
            path = path.rstrip('/')
        elif path == '':
            path = '/'
        
        if scheme in ('http', 'https'):
            scheme = 'https'
        
        normalized = f"{scheme}://{netloc}{path}"
        if query:
            normalized += f"?{query}"
        
        return normalized
        
    except Exception:
        return url.split('#')[0] if '#' in url else url

# used for loop-detection
def get_subdomain(url) -> str:
    '''returns up until the subdomain of a url assuming it has been normalized
        example: get_subdomain(self, "https://ics.uci.edu/~eppstein/pix/ham/Sara2.html) will return
        "https://ics.uci/edu/~eppstein/pix"
    '''
    parsed = urlparse(url)

    scheme = parsed.scheme  # https
    netloc = parsed.netloc  # ics.uci.edu
    path = parsed.path  # /~eppstein/pix/ham/Sara2.html

    if path.startswith('/') and len(path) > 1: # checks if there is even a subdomain to begin with
        split_path: list[str] = path[1:].split("/")

        if(len(split_path) == 1):   # if path = /~eppstein/, new path is itself
            path = "/" + split_path[0] + "/"
        else:   # if path = /~eppstein/pix/ham/Sara2.html, new path = /~eppstein/pix/; can adjust for finer loop detection
            path = "/" + split_path[0] + "/" + split_path[1] + "/"

    return f"{scheme}://{netloc}{path}"

def get_deepest_link(url) -> str:
    '''returns the deepest link of a url without the html file'''
    parsed = urlparse(url)

    scheme = parsed.scheme # https
    netloc = parsed.netloc 
    path = parsed.path

    if path.startswith('/') and len(path) > 1:
        split_path: list[str] = path[1:].split("/")
    else:
        split_path = []
        
    if(len(split_path) <= 1):   # if url has no directories and is just html page
        path = "/"
    else:
        path = "/"
        for i in range(0, len(split_path) - 1):
            path += split_path[i] + "/"

    return f"{scheme}://{netloc}{path}"


def _load_stopwords():
    stopwords_text = "a about above after again against all am an and any are aren't as at be because been before being below between both but by can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves nbsp"
    return set(stopwords_text.split())


def process_content(content):
    if not content:
        return 0, []

    soup = BeautifulSoup(content, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    text = soup.get_text(" ", strip=True)

    words = _WORD_RE.findall(text.lower())
    stopwords = _load_stopwords()

    filtered_words = []
    for word in words:
        if len(word) > 2 and word not in stopwords:
            filtered_words.append(word)

    return len(words), filtered_words


def compute_simhash(content, hash_bits=64):
    """
    Compute SimHash fingerprint for content.
    Returns an integer hash representing the page.
    """
    if not content:
        return 0
    
    try:
        soup = BeautifulSoup(content, "lxml")
        for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
            tag.decompose()
        text = soup.get_text(" ", strip=True)
        
        words = text.lower().split()
        stopwords = _load_stopwords()

        features = []
        for word in words:
            if len(word) > 2 and word not in stopwords:
                features.append(word)
        
        if not features:
            return 0
        
        bit_counts = [0] * hash_bits
        
        for word in features:
            word_hash = hash(word) & ((1 << hash_bits) - 1)
            for i in range(hash_bits):
                if word_hash & (1 << i):
                    bit_counts[i] += 1
                else:
                    bit_counts[i] -= 1
        simhash = 0

        for i in range(hash_bits):
            if bit_counts[i] >= 0:
                simhash |= (1 << i)
                
        return simhash
    except Exception:
        return 0


def calculate_page_fingerprint(content):
    """
    Calculate a fingerprint for a page using SimHash.
    Returns an integer hash.
    """
    return compute_simhash(content)


def hamming_distance(hash1, hash2):
    """
    Calculate Hamming distance between two hashes.
    Returns number of differing bits.
    """
    if hash1 == 0 and hash2 == 0:
        return 0
    
    # XOR to find differing bits
    diff = hash1 ^ hash2
    
    # Count set bits
    count = 0
    while diff:
        count += diff & 1
        diff >>= 1
    
    return count


def is_duplicate(fingerprint1, fingerprint2, max_distance=3):
    """
    Check if two page fingerprints are duplicates using Hamming distance.
    Returns True if Hamming distance <= max_distance (default 3).
    """
    if fingerprint1 == 0 and fingerprint2 == 0:
        return False
    
    if fingerprint1 == 0 or fingerprint2 == 0:
        return False
    
    distance = hamming_distance(fingerprint1, fingerprint2)
    return distance <= max_distance

