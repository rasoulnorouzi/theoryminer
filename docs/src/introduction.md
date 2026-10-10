# theoryminer

`theoryminer` turns a set of research papers into a causal map.

You give it PDF files. It finds the sentences that claim a cause and an effect, and it extracts
each cause → effect pair. Then it brings together the different names that authors use for the
same construct. The result is an interactive map. Each arrow leads back to the sentences that
claim it, with the page and the DOI of each paper.

## The pipeline

```
PDF ──harvest()──► sentences ──causenet()──► relations (cause span → effect span)
                                                  │
              ┌───────────────────────────────────┼───────────────────────────┐
              ▼                                   ▼                           ▼
standardize_constructs()            pairwise_grouping() / clusterer()      (spans)
span → top-k thesaurus concepts     spans → groups of similar spans
                                                  │
                                  ┌───────────────┴───────────────┐
                                  ▼                               ▼
                        standardize_groups()               label_groups()
                        group → thesaurus concept          group → label from its own words
                                  └───────────────┬───────────────┘
                                                  ▼
                        causal_map() ──► draw_map()  the interactive page
                                     └─► save_map()  CSV tables and GraphML
```

Two more stages feed the pipeline with papers. `extract_references()` finds the DOIs that your
papers cite. `download_papers()` downloads the open-access PDFs of those DOIs. Together they run a
snowball search: the papers of one round give the references of the next round.

## What each step gives you

| Step | Function | Result |
|---|---|---|
| Read the PDFs | `harvest()` | clean sentences, and a drop log with the reason for each dropped line |
| Find causal claims | `causenet()` | one relation for each cause → effect pair |
| Group the names | `pairwise_grouping()`, `clusterer()` | groups of spans that mean the same construct |
| Name the groups | `label_groups()`, `standardize_groups()` | a name for each group, from its own words or from a thesaurus |
| Build the map | `causal_map()` | nodes, edges and the hidden edges |
| Show and save | `draw_map()`, `save_map()` | an offline HTML page, CSV tables and a GraphML file |

## The rules behind the results

- **Nothing is deleted.** A step that drops a sentence, or hides an edge, marks it and records the
  reason. The drop log and the hidden edges are part of the result.
- **A span stays as the author wrote it.** The only change is a repair of the tokenizer output.
  That repair removes no word.
- **Every result leads back to its source.** An edge knows its relations. A relation knows its
  sentence, its page and its paper.
- **A thesaurus is optional.** The package includes the ELSST thesaurus. Every step that uses it
  has a twin that needs no thesaurus.

## Status

Extraction, the grouping and naming of constructs, and the causal map work. The evaluation
against a theory specification that people made by hand is planned.

## Where to start

1. [Install](install.md) the package.
2. Run the [quick start](quickstart.md) on the sample papers.
3. Read the [guide](guide/harvest.md) for the step that you need.

The [tutorial notebook](tutorials.md) runs every function and every setting on 7 sample papers.
