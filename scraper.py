import re
from urllib.parse import urljoin, urlparse


def scraper(url, resp):
    links = extract_next_links(url, resp)
    return [link for link in links if is_valid(link)]

def extract_next_links(url, resp):
    # Implementation required.
    # url: the URL that was used to get the page
    # resp.url: the actual url of the page
    # resp.status: the status code returned by the server. 200 is OK, you got the page. Other numbers mean that there was some kind of problem.
    # resp.error: when status is not 200, you can check the error here, if needed.
    # resp.raw_response: this is where the page actually is. More specifically, the raw_response has two parts:
    #         resp.raw_response.url: the url, again
    #         resp.raw_response.content: the content of the page!
    # Return a list with the hyperlinks (as strings) scrapped from resp.raw_response.content
    
    links = []

    if resp.status == 200 and resp.raw_response and resp.raw_response.content:
        try:
            html_content = resp.raw_response.content.decode('utf-8', errors='ignore')
            
            href_pattern = r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>'
            
            matches = re.findall(href_pattern, html_content, re.IGNORECASE)
            
            for href in matches:
                absolute_url = urljoin(resp.url, href)
                absolute_url = absolute_url.split('#')[0]

                if '?' in absolute_url and not any(param in absolute_url for param in ['=', '&']):
                    absolute_url = absolute_url.split('?')[0]
                
                links.append(absolute_url)
                
        except Exception as e:
            print(f"Error parsing HTML content: {e}")
            return []
    
    return links

def is_valid(url):
    # Decide whether to crawl this url or not. 
    # If you decide to crawl it, return True; otherwise return False.
    # There are already some conditions that return False.
    try:
        parsed = urlparse(url)
        
        if parsed.scheme not in ["http", "https"]:
            return False

        allowed_domains = [
            "ics.uci.edu",
            "www.ics.uci.edu", 
            "cs.uci.edu",
            "www.cs.uci.edu",
            "informatics.uci.edu", 
            "www.informatics.uci.edu",
            "stat.uci.edu",
            "www.stat.uci.edu"
        ]
        
        if parsed.netloc.lower() not in allowed_domains:
            return False
        
        if re.match(
            r".*\.(css|js|bmp|gif|jpe?g|ico"
            + r"|png|tiff?|mid|mp2|mp3|mp4"
            + r"|wav|avi|mov|mpeg|ram|m4v|mkv|ogg|ogv|pdf"
            + r"|ps|eps|tex|ppt|pptx|doc|docx|xls|xlsx|names"
            + r"|data|dat|exe|bz2|tar|msi|bin|7z|psd|dmg|iso"
            + r"|epub|dll|cnf|tgz|sha1"
            + r"|thmx|mso|arff|rtf|jar|csv"
            + r"|rm|smil|wmv|swf|wma|zip|rar|gz)$", parsed.path.lower()):
            return False
        
        if len(url) > 200:
            return False
            
        if len(parsed.path.split('/')) > 10:
            return False
        
        return True

    except Exception as e:
        print(f"Error parsing URL {url}: {e}")
        return False
