"""tmsr — the source "tmsr-doi-downloader" (PyPI, Apache-2.0, eScience TMSR team).

pip install theoryminer installs it on Python 3.11 or newer (since 0.2.1). It tries CORE
(core_api_key=), Crossref, doi.org, Google Scholar (serpapi_key=, a paid service) and Unpaywall
(email=). A key that you do not pass comes from its environment variable: CORE_API_KEY,
SERPAPI_KEY or UNPAYWALL_EMAIL.

tmsr-doi-downloader writes a cache (database.db) and a log (benchmark/) into the working folder.
So this module runs it inside CACHE_DIR, not in your folder.
"""

import contextlib
import io
import os

CACHE_DIR = os.path.join(os.environ.get("THEORYMINER_CACHE_DIR", os.path.expanduser("~/.cache/theoryminer")),
                         "downloader")


def _set_keys(email, core_api_key, serpapi_key):
    """Give the keys to the sources of tmsr-doi-downloader. A key that is None is not changed.

    The sources read their keys once, at import, from the environment variables. So a key
    that you pass must be set on the source module. A key that you do not pass keeps the
    value of its environment variable.
    """
    from doi_downloader.plugins import coreacuk, googlescholar, unpaywall

    if email is not None:
        unpaywall.UNPAYWALL_EMAIL = email
    if core_api_key is not None:
        coreacuk.CORE_API_KEY = core_api_key
    if serpapi_key is not None:
        googlescholar.SERPAPI_KEY = serpapi_key


def _tmsr_download(doi, path, email, core_api_key, serpapi_key):
    """Try tmsr-doi-downloader. Return "" when it saved the PDF into path, else why not.

    It runs in CACHE_DIR, and its output is silenced.
    """
    os.makedirs(CACHE_DIR, exist_ok=True)
    folder = os.path.dirname(os.path.abspath(path))
    here = os.getcwd()
    os.chdir(CACHE_DIR)                               # its cache and its log go here, not into your folder
    try:
        with contextlib.redirect_stdout(io.StringIO()):
            from doi_downloader import doi_downloader as ddl
            _set_keys(email, core_api_key, serpapi_key)
            saved = ddl.download(doi, output_dir=folder, enable_benchmark=False)
    except ImportError:
        return "not installed (it needs Python 3.11 or newer)"
    except Exception as error:                        # one failed source must not stop the run
        return type(error).__name__
    finally:
        os.chdir(here)
    if not saved:
        return "found no PDF"
    os.replace(saved, path)                           # its file name differs from ours
    return ""
