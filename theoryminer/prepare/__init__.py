"""prepare — stage 1: PDF files -> clean sentences, and the DOI and title of each paper.

    harvest.py   harvest(): the text of each PDF, cleaned and split into sentences
    dois.py      extract_dois(): the DOI and title of each paper; extract_references(): the DOIs it cites

Import the functions from the package root: from theoryminer import harvest, extract_dois.
This file imports nothing on purpose. If it imported the function harvest, the name
theoryminer.prepare.harvest would give the function, not the module harvest.py.
"""
