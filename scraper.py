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

ALLOWED_DOMAINS = {
    "ics.uci.edu", "www.ics.uci.edu", "cs.uci.edu", "www.cs.uci.edu",
    "informatics.uci.edu", "www.informatics.uci.edu", "stat.uci.edu", "www.stat.uci.edu"
}

def scraper(url, resp, frontier):
    # URL is already normalized when it comes from frontier
    normalized_url = url
    
    if normalized_url in frontier.unique_urls:
        return []
        
    links = extract_next_links(url, resp)
    
    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        try:
            content = resp.raw_response.content.decode('utf-8', errors='ignore')
            frontier.add_page(normalized_url, content)
        except Exception as e:
            frontier.add_page(normalized_url)
    else:
        frontier.add_page(normalized_url)
    
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
            
            absolute_url = urljoin(resp.url, href)
            
            absolute_url = absolute_url.split('#')[0]
            
            if '?' in absolute_url:
                has_real_params = '=' in absolute_url or '&' in absolute_url
                if not has_real_params:
                    absolute_url = absolute_url.split('?')[0]
            
            links.append(absolute_url)
            
    except Exception as e:
        print(f"error in parsing links, {e}")
        return []
    
    return links

def is_valid(url):
    if len(url) > 200:
        return False
    
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ("http", "https"):
            return False

        netloc_lower = parsed.netloc.lower()
        if netloc_lower not in ALLOWED_DOMAINS and not (netloc_lower.endswith('.uci.edu') or netloc_lower == 'uci.edu'):
            return False
        
        if FILE_EXTENSION_PATTERN.match(parsed.path.lower()):
            return False
            
        if len(parsed.path.split('/')) > 10:
            return False
        
        return True

    except Exception as e:
        print(f"error in parsing url, {e}")
        return False
