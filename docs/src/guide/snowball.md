# A snowball round

A snowball search starts from seed papers and follows their references. One round has four steps:

1. Find the DOIs in the references of the seed papers.
2. Download the PDFs of those DOIs.
3. Read the new papers and draw their map.
4. Find the references of the new papers: the DOIs for the next round.

```python
from theoryminer import (extract_references, download_papers, harvest, causenet,
                         pairwise_grouping, label_groups, causal_map, draw_map)

# 1. The references of the seed paper
refs = extract_references("sample_files/schutz_2025_loneliness_social_support.pdf")

# 2. Their open-access PDFs, CC BY only
report = download_papers(refs, "outputs/round_2", licences=["cc-by"], email="you@your-uni.edu")

# 3. The map of the new papers
data = harvest("outputs/round_2")
relations = causenet(data["sentences"])
names = label_groups(pairwise_grouping(relations))
cmap = causal_map(relations, names)
draw_map(cmap, save="outputs/round_2_map.html")

# 4. The DOIs for round 3
next_refs = extract_references("outputs/round_2", save="outputs/round_3_dois.csv")
```

## What the tutorial run gave

| Step | Result |
|---|---|
| 1. References of the seed | 74 DOIs |
| 2. Download, CC BY only | 45 papers left out by their licence; 26 of the 29 CC BY papers in the folder |
| 3. The new papers | 4,450 sentences, 1,555 relations, a map with 72 nodes and 66 shown edges |
| 4. References of the new papers | 472 DOIs; 26 of them cited by 2 or more papers |

`licences=["cc-by"]` keeps only the papers whose text may be shown and shared. Leave it out to
download every open-access paper.

The DOIs that more papers cite come first in the output of `extract_references()`. They are a good
start for the next round.

## Notes

- The download writes `downloads.csv` into the folder. `harvest()` reads it, so each sentence knows
  the DOI of its paper, also when the PDF does not print its DOI.
- A stopped download can go on: a PDF that is already in the folder is not downloaded again.
- See [Download papers](download.md) for the sources and the limits.
