"""fetch — the network part of the downloader: one GET, robots.txt, the wait per site, the PDF check.

Every request of the downloader goes through _get(). It waits WAIT seconds between two requests to
the same site, keeps the cookies of the run (some sites set a cookie on a redirect), and gives the
reason of a failure as a short note ("HTTP 403", "timeout").
"""

import html
import http.client
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.request
import urllib.robotparser
from urllib.parse import urljoin, urlsplit

USER_AGENT = "theoryminer (https://github.com/rasoulnorouzi/theoryminer)"
ACCEPT = "application/pdf, text/html;q=0.9, */*;q=0.8"     # a PDF first, else the landing page
WAIT = 1.0              # seconds between two requests to the same site, as tmsr-doi-downloader waits
TIMEOUT = 60            # seconds before a request gives up (a large PDF on a slow link needs time)
PDF_START = b"%PDF-"    # the first bytes of every PDF file
PDF_START_WINDOW = 1024     # some servers put a few bytes before "%PDF-"; the PDF standard permits 1024

# A <meta> tag. Matches '<meta name="citation_pdf_url" content="/a.pdf">'; not '<link rel="alternate">'.
META_TAG = re.compile(r"<meta\s[^>]*>", re.IGNORECASE)
# The name that Google Scholar reads for the PDF link of a paper.
# Matches 'name="citation_pdf_url"'; not 'name="citation_title"'.
PDF_META_NAME = re.compile(r"""name\s*=\s*["']citation_pdf_url["']""", re.IGNORECASE)
# The value of a meta tag. Matches 'content="https://a.org/a.pdf"'; not 'name="a"'.
META_CONTENT = re.compile(r"""content\s*=\s*["']([^"']+)["']""", re.IGNORECASE)

_OPENER = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
_ROBOTS = {}            # {site: robots.txt parser}, read once per site and run
_LAST_REQUEST = {}      # {site: the time of the last request}, for the wait per site


def _site(url):
    """Return the scheme and the host of a url.

    Example:
        >>> _site("https://www.frontiersin.org/articles/10.3389/x/pdf")
        'https://www.frontiersin.org'
    """
    return "{0.scheme}://{0.netloc}".format(urlsplit(url))


def _wait_for(site):
    """Sleep until WAIT seconds have passed since the last request to the site."""
    last = _LAST_REQUEST.get(site)
    if last is None:
        return
    pause = WAIT - (time.time() - last)
    if pause > 0:
        time.sleep(pause)


def _get(url):
    """Return (body, final_url, note) of a GET request. The note is "" on success, else the reason.

    The final url is the url after the redirects. The step waits WAIT seconds between two
    requests to the same site. It does not wait between two different sites.
    """
    site = _site(url)
    _wait_for(site)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": ACCEPT})
    try:
        with _OPENER.open(request, timeout=TIMEOUT) as response:
            return response.read(), response.geturl(), ""
    except urllib.error.HTTPError as error:
        return b"", url, f"HTTP {error.code}"
    except TimeoutError:
        return b"", url, "timeout"
    except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
        return b"", url, type(error).__name__
    finally:
        _LAST_REQUEST[site] = time.time()


def _get_json(url):
    """Return (data, note) of a GET request that gives JSON. data is None when the request fails."""
    body, _, note = _get(url)
    if note:
        return None, note
    try:
        return json.loads(body), ""
    except ValueError:
        return None, "not JSON"


def _robots_allow(url):
    """Return True when the robots.txt of the site allows a robot to read the url.

    A site without a robots.txt allows every url.
    """
    site = _site(url)
    if site not in _ROBOTS:
        body, _, _ = _get(site + "/robots.txt")
        parser = urllib.robotparser.RobotFileParser()
        parser.parse(body.decode("utf-8", "replace").splitlines())
        _ROBOTS[site] = parser
    return _ROBOTS[site].can_fetch("*", url)


def _is_pdf(body):
    """Return True when the bytes are a PDF file.

    Example:
        >>> _is_pdf(b"%PDF-1.7 ..."), _is_pdf(b"<html>")
        (True, False)
    """
    return PDF_START in body[:PDF_START_WINDOW]


def _pdf_link_in_page(body, page_url):
    """Return the PDF link of an HTML page (its citation_pdf_url meta tag), or "" when it has none.

    Most publishers and repositories put this tag on the landing page of a paper for Google
    Scholar. A relative link is made absolute with the url of the page.

    Example:
        >>> _pdf_link_in_page(b'<meta name="citation_pdf_url" content="/x.pdf?a=1&amp;b=2">', "https://a.org/p")
        'https://a.org/x.pdf?a=1&b=2'
    """
    text = body[:500_000].decode("utf-8", "replace")    # the meta tags are in the head of the page
    for tag in META_TAG.findall(text):
        if not PDF_META_NAME.search(tag):
            continue
        content = META_CONTENT.search(tag)
        if content:
            return urljoin(page_url, html.unescape(content.group(1)))
    return ""


def _fetch(url, respect_robots):
    """Return (body, final_url, note) of a GET request that robots.txt allows."""
    if respect_robots and not _robots_allow(url):
        return b"", url, "robots.txt blocks it"
    return _get(url)


def _try_url(url, path, respect_robots):
    """Save the PDF of one url into path. Return "" when the PDF is saved, else why not.

    A url can give the PDF itself, or an HTML page (a landing page or a repository page).
    For a page, the step follows its citation_pdf_url meta tag once.
    """
    body, page_url, note = _fetch(url, respect_robots)
    if note:
        return note
    if not _is_pdf(body):
        pdf_url = _pdf_link_in_page(body, page_url)
        if not pdf_url or pdf_url == url:
            return "not a PDF"
        body, _, note = _fetch(pdf_url, respect_robots)
        if note:
            return f"{note} (the PDF link of the page)"
    if not _is_pdf(body):
        return "not a PDF"
    with open(path, "wb") as fh:
        fh.write(body)
    return ""


def _fetch_pdf(urls, path, respect_robots, tried):
    """Try the urls in turn until one gives a PDF. Return "" when the PDF is saved, else the notes.

    Args:
        urls: The links of one source.
        path: Where to save the PDF.
        respect_robots: True: skip a url that robots.txt does not allow.
        tried: The urls that an earlier source tried for this DOI. The step skips them and adds
            the new ones. The step changes this set in place.
    """
    notes = []
    for url in urls:
        if url in tried:
            continue
        tried.add(url)
        note = _try_url(url, path, respect_robots)
        if not note:
            return ""
        notes.append(f"{urlsplit(url).netloc} {note}")
    if not notes:
        return "no new link"
    return ", ".join(notes)
