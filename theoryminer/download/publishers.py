"""publishers — one plugin per publisher, in the style of a Zotero translator.

Zotero has one translator per site. Each translator knows how a publisher builds the PDF link of
an article. This module does the same with one plugin per publisher, keyed by the DOI prefix
(10.1007 is Springer). A plugin turns a DOI into the direct PDF link of the publisher.

Each plugin is a dict:
    name      the publisher, for the report and the log
    prefixes  the DOI prefixes it handles (a DOI starts with "10.<prefix>/")
    build     a function build(doi, work) -> a list of direct PDF links (work is the OpenAlex
              record, for the volume, the issue and the ISSN that some links need)

A plugin is here only when a plain request gets the PDF. Wiley, Taylor & Francis, SAGE, MDPI,
Annual Reviews and Emerald give their PDFs only to a browser that passes their bot check, so a
plugin for them gives nothing. The package does not use a browser or log in to a publisher site
(a decision of 2026-10-10). Their open papers often come through the other sources: a repository
copy in OpenAlex, PubMed Central or Europe PMC.

To add a journal, add one plugin to PLUGINS. Nothing else changes.
"""


def _springer_pdf(doi, work):
    """Return the Springer direct PDF link. Springer serves it to a plain request.

    The robots.txt of link.springer.com does not allow this path. So the link gives a PDF only
    with download_papers(..., respect_robots=False).
    """
    return [f"https://link.springer.com/content/pdf/{doi}.pdf"]


def _frontiers_pdf(doi, work):
    """Return the Frontiers direct PDF link. Frontiers serves it to a plain request."""
    return [f"https://www.frontiersin.org/articles/{doi}/pdf"]


# The plugins, each for one publisher. The order does not matter: a DOI prefix picks one plugin.
PLUGINS = [
    {"name": "Springer", "prefixes": ["10.1007", "10.1057", "10.1186", "10.3758"], "build": _springer_pdf},
    {"name": "Frontiers", "prefixes": ["10.3389"], "build": _frontiers_pdf},
]


def _prefix(doi):
    """Return the prefix of a DOI: the part before the first "/".

    Example:
        >>> _prefix("10.3389/feduc.2021.618655")
        '10.3389'
    """
    return doi.split("/", 1)[0]


def plugin_for(doi):
    """Return the plugin that handles a DOI, or None when no plugin does.

    Example:
        >>> plugin_for("10.3389/feduc.2021.618655")["name"]
        'Frontiers'
        >>> plugin_for("10.9999/unknown") is None
        True
    """
    prefix = _prefix(doi)
    for plugin in PLUGINS:
        if prefix in plugin["prefixes"]:
            return plugin
    return None


def direct_pdf_urls(doi, work):
    """Return the publisher's direct PDF links for a DOI, or [] when no plugin handles it.

    Example:
        >>> direct_pdf_urls("10.3389/feduc.2021.618655", {})
        ['https://www.frontiersin.org/articles/10.3389/feduc.2021.618655/pdf']
    """
    plugin = plugin_for(doi)
    if plugin is None:
        return []
    return plugin["build"](doi, work)
