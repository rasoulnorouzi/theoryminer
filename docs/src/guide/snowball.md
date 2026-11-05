# A snowball round

A snowball search finds more papers from the papers that you have. You start with a few papers,
the seed papers. You read their reference lists, and you get the cited papers. These new papers
are the second round. Their reference lists give the third round.

The package does one round in four steps:

1. `extract_references()` reads the seed papers and lists the DOIs in their reference lists.
2. `download_papers()` downloads the free PDFs of these DOIs into a new folder.
3. `harvest()`, `causenet()` and the other functions make the causal map of the new papers.
4. `extract_references()` reads the new papers. Their DOIs are the input of the next round.

## The folders

The example below uses these folders. You can use other names.

| Folder | What it holds |
|---|---|
| `sample_files/` | the seed papers (round 1). You put them there. |
| `outputs/round_2/` | the papers of round 2. `download_papers()` makes the folder and puts the PDFs in it. |
| `outputs/` | the map of round 2, and the DOIs for round 3 |

## The code

```python
from theoryminer import (extract_references, download_papers, harvest, causenet,
                         clusterer, label_groups, causal_map, draw_map)

# 1. Get the DOIs that the seed papers cite.
refs = extract_references("sample_files")

# 2. Download the cited papers into the folder outputs/round_2.
report = download_papers(
    refs,                          # the DOIs from step 1
    "outputs/round_2",             # the folder for the PDFs
    licences=["cc-by"],            # only the papers with a CC BY licence
    email="you@your-uni.edu",      # your email address
)

# 3. Make the causal map of the new papers.
data = harvest("outputs/round_2")
relations = causenet(data["sentences"])
groups = clusterer(relations)
names = label_groups(groups)
cmap = causal_map(relations, names)
draw_map(cmap, save="outputs/round_2_map.html")

# 4. Get the DOIs that the new papers cite. Save them for round 3.
next_refs = extract_references("outputs/round_2", save="outputs/round_3_dois.csv")
```

## Notes

- Not all DOIs give a PDF. Only papers with a free copy can be downloaded. Look at the `status`
  and `note` of each row of `report` to see why a DOI has no PDF.
- `licences=["cc-by"]` keeps only the papers that you can share. Remove it to download every free
  paper.
- The DOIs that more of your papers cite come first in `next_refs`. Start the next round with
  them.
- When the download stops, run it again. It does not download a PDF that is already in the folder.
- To start round 3, give `next_refs`, or the file `outputs/round_3_dois.csv`, to
  `download_papers()`.

See [Download papers](download.md) and [DOIs and references](dois.md) for all the arguments.
