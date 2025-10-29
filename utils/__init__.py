import os
import logging
import re
from hashlib import sha256
from urllib.parse import urlparse
from collections import Counter

# Precompiled regex patterns for text processing
_STYLE_TAG_RE = re.compile(r'<style[^>]*>.*?</style>', flags=re.DOTALL | re.IGNORECASE)
_SCRIPT_TAG_RE = re.compile(r'<script[^>]*>.*?</script>', flags=re.DOTALL | re.IGNORECASE)
_HTML_TAG_RE = re.compile(r'<[^>]+>')
_CSS_PROP_RE = re.compile(r'[a-zA-Z-]+\s*:\s*[^;]+;?')
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
    # everything other than scheme.
    return sha256(
        f"{parsed.netloc}/{parsed.path}/{parsed.params}/"
        f"{parsed.query}/{parsed.fragment}".encode("utf-8")).hexdigest()

def normalize(url):
    """Normalize URL by removing fragments, converting to lowercase, removing www, and standardizing paths"""
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
def get_subdomain(url):
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


# Cache stopwords to avoid reloading on every call
_STOPWORDS_CACHE = None

def _load_stopwords():
    """Load common English stopwords for text processing (cached)"""
    global _STOPWORDS_CACHE
    if _STOPWORDS_CACHE is None:
        stopwords_text = "a about above after again against all am an and any are aren't as at be because been before being below between both but by can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's i i'd i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once only or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those through to under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours yourself yourselves"
        _STOPWORDS_CACHE = set(stopwords_text.split())
    return _STOPWORDS_CACHE


def process_content(content):
    """Process HTML content to extract meaningful words, removing HTML tags, CSS, and scripts"""
    # Precompiled regexes for performance
    clean_text = _STYLE_TAG_RE.sub(' ', content)
    clean_text = _SCRIPT_TAG_RE.sub(' ', clean_text)
    clean_text = _HTML_TAG_RE.sub(' ', clean_text)
    clean_text = _CSS_PROP_RE.sub(' ', clean_text)

    words = _WORD_RE.findall(clean_text.lower())
    stopwords = _load_stopwords()
    filtered_words = [word for word in words if len(word) > 2 and word not in stopwords]
    return len(words), filtered_words


