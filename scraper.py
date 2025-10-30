import re
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from utils import normalize

FILE_EXTENSION_PATTERN = re.compile(
    r".*\.(css|js|bmp|gif|jpe?g|ico"
    + r"|png|tiff?|mid|mp2|mp3|mp4"
    + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
    + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
    + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
    + r"|epub|dll|cnf|tgz|sha1"
    + r"|thmx|mso|arff|rtf|jar|csv"
    + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$"
)

# Only allow these bases and their subdomains
ALLOWED_SUFFIXES = (
    "ics.uci.edu",
    "cs.uci.edu",
    "informatics.uci.edu",
    "stat.uci.edu",
)

# Blacklisted words - URLs containing any of these should be skipped
URL_BLACKLIST = {"week", "year", "month", "ical", "doku", "tribe", "twitter", "facebook", "instagram", "youtube"}
_SKIP_SCHEMES = ("mailto:", "javascript:", "tel:")

def scraper(url, resp, frontier):
    # URL is already normalized when it comes from frontier
    normalized_url = url
    
    if normalized_url in frontier.unique_urls:
        return []
        
    links = extract_next_links(url, resp)
    
    word_count = 0
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        try:
            content = resp.raw_response.content.decode('utf-8', errors='ignore')
            word_count = frontier.add_page(normalized_url, content)
        except Exception as e:
            word_count = frontier.add_page(normalized_url)
    else:
        word_count = frontier.add_page(normalized_url)
    
    # Only add links to frontier if page has at least 50 words
    if word_count < 50:
        return []
    
    valid_links = []
    for link in links:
        if is_valid(link):
            normalized_link = normalize(link)
            if normalized_link not in frontier.unique_urls:
                valid_links.append(link)  # Return original link for frontier.add_url
    
    return valid_links

def extract_next_links(url, resp):
    if resp.status != 200 or not resp.raw_response or not resp.raw_response.content:
        return []
    
    try:
        html_content = resp.raw_response.content.decode('utf-8', errors='ignore')
        soup = BeautifulSoup(html_content, 'html.parser')
        
        links = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if not href:
                continue
            low = href.lower()
            if low.startswith(_SKIP_SCHEMES) or low.startswith('#'):
                continue

            absolute_url = urljoin(resp.url, href)
            if '#' in absolute_url:
                absolute_url = absolute_url.split('#', 1)[0]
            if '?' in absolute_url and ('=' not in absolute_url and '&' not in absolute_url):
                absolute_url = absolute_url.split('?', 1)[0]
            links.append(absolute_url)
            
    except Exception as e:
        print(f"error in parsing links, {e}")
        return []
    
    return links

def is_valid(url):
    if len(url) > 200:
        return False
    
    # Check if URL contains any blacklisted words (case-insensitive)
    url_lower = url.lower()
    for blacklisted_word in URL_BLACKLIST:
        if blacklisted_word in url_lower:
            return False
    
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ("http", "https"):
            return False

        netloc_lower = parsed.netloc.lower()
        # Allow only the four specified bases (including www) and their subdomains
        if not any(
            netloc_lower == suffix or
            netloc_lower == ("www." + suffix) or
            netloc_lower.endswith('.' + suffix)
            for suffix in ALLOWED_SUFFIXES
        ):
            return False
        
        path_lower = parsed.path.lower()  # Reuse lowercase path for both checks
        if FILE_EXTENSION_PATTERN.match(path_lower):
            return False
            
        # Optimize depth check - count '/' instead of splitting
        if path_lower.count('/') > 10:
            return False
        
        return True

    except Exception as e:
        print(f"error in parsing url, {e}")
        return False
