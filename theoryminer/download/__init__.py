"""download — stage 0: a list of DOIs -> PDF files.

    papers.py       download_papers(): the PDF of each DOI, with one status row per DOI
    sources.py      one finder per open-access source (OpenAlex, PMC, Unpaywall, ...)
    publishers.py   one plugin per publisher: a DOI -> the direct PDF link
    fetch.py        the network part: one GET, robots.txt, the wait per site, the PDF check
    tmsr.py         the opt-in source tmsr-doi-downloader

Import the function from the package root: from theoryminer import download_papers.
"""

from .papers import download_papers

__all__ = ["download_papers"]
