# Standardization strategies, with `leaves_only` on and off

_Companion to `TUTORIAL.ipynb` section 4. Every text and score below is real: it was
printed by `strategy_text` and `standardize_constructs` on ELSST R5 with `allmpnet`._

## 1. What a strategy is

`standardize_constructs` matches a span to a taxonomy concept by embedding both and taking the
cosine. The span is embedded as it is. The concept has no natural text, so a **strategy** is
the recipe that builds one. Six recipes exist. They use four fields of a taxonomy entry:

| field | meaning | SELF-ESTEEM |
|---|---|---|
| `leaf` | the concept's own label | `SELF-ESTEEM` |
| `path` | the chain of broader concepts from a top concept down to it | `IDENTITY > PERSONAL IDENTITY > SELF-ESTEEM` |
| `parents` | the broader concepts, nearest first | `PERSONAL IDENTITY, IDENTITY` |
| `alt` | the entry terms (synonyms) | `SELF-ACCEPTANCE, SELF-CONFIDENCE, SELF-RESPECT` |
| `note` | the English scope note or definition, often empty | (empty) |

Everything is lowercased before embedding.

| strategy | recipe | SELF-ESTEEM |
|---|---|---|
| `leaf` | label | `self-esteem` |
| `path` | path | `identity > personal identity > self-esteem` |
| `anchor` | label: path | `self-esteem: identity > personal identity > self-esteem` |
| `context` | label is related to parents | `self-esteem is related to personal identity, identity` |
| `bracket` | label (parents) | `self-esteem (personal identity, identity)` |
| `enriched` | label. synonyms. note. path | `self-esteem. self-acceptance; self-confidence; self-respect. identity > personal identity > self-esteem` |

Each strategy is one answer to one question: *how much of the tree should the concept vector
carry?* `leaf` carries none. `path`, `anchor`, `context`, `bracket` carry the ancestors in four
phrasings. `enriched` carries the ancestors and, more important, the synonyms.

## 2. What `leaves_only` is

ELSST is a tree. A **leaf** has no narrower concept under it. A **branch** has children.

```
MOTIVATION                    branch (and a top concept: no parent)
├── ASPIRATION                leaf
└── INCENTIVES                leaf

WELL-BEING (HEALTH)           branch (top concept)
├── PSYCHOLOGICAL WELL-BEING  leaf
├── LIFESTYLE AND HEALTH      leaf
├── AGEING                    leaf
└── ENVIRONMENTAL EXPOSURE    leaf

IDENTITY > PERSONAL IDENTITY > SELF-ESTEEM     leaf, two paths (also under IMAGE)
```

| | `leaves_only=True` (default) | `leaves_only=False` |
|---|---|---|
| who can be an answer | the 2,417 leaves | all 3,436 concepts |
| entries embedded | 2,661 | 3,739 |
| cache file | `elsst_<strategy>_<model>_leaves.npy` | `elsst_<strategy>_<model>_all.npy` |
| where a span lands | the bottom of the tree, always | any level |

The switch changes **which concepts may answer**. It does not change any recipe or any
score. A leaf's text is the same under both settings.

### How a branch becomes an entry

With `leaves_only=False` every branch gets an entry of the same shape as a leaf entry: its
own label as `leaf`, the path from a top concept down to itself, its own parents. The six
recipes then apply unchanged. Two cases:

**A branch with parents** (PERSONAL IDENTITY, child of IDENTITY and of IMAGE):

| strategy | text |
|---|---|
| `leaf` | `personal identity` |
| `path` | `identity > personal identity` |
| `anchor` | `personal identity: identity > personal identity` |
| `context` | `personal identity is related to identity` |
| `bracket` | `personal identity (identity)` |
| `enriched` | `personal identity. <synonyms>. identity > personal identity` |

**A top concept** (no parent; 247 of them in R5, MOTIVATION and WELL-BEING (HEALTH) among
them). The path is the label alone, the parents list is empty, and the recipes collapse:

| strategy | MOTIVATION |
|---|---|
| `leaf` | `motivation` |
| `path` | `motivation` |
| `anchor` | `motivation: motivation` |
| `context` | `motivation` |
| `bracket` | `motivation` |
| `enriched` | `motivation. motivation` |

`anchor` and `enriched` repeat the label for a top concept because the path *is* the label.
Harmless for the cosine, but not pretty. It is the one place where a recipe would deserve a
special case (skip the path when it equals the label).

### A leaf with two paths

SELF-ESTEEM sits under IDENTITY and under IMAGE. It gets **two entries**, one per path, under
both settings. The label, synonyms and note are the same in both; the path and parents differ:

| strategy | entry 1 | entry 2 |
|---|---|---|
| `leaf` | `self-esteem` | `self-esteem` (identical vector) |
| `path` | `identity > personal identity > self-esteem` | `image > personal identity > self-esteem` |
| `bracket` | `self-esteem (personal identity, identity)` | `self-esteem (personal identity, image)` |

At lookup the span is scored against both and the best score is kept for the concept. No
path is preferred by depth or by any other rule; the span picks the path that fits it. 244 of
the 2,661 leaf entries come from this (97 of those concepts also have synonyms). Under `leaf`
the two vectors are identical and the duplicate falls away in the de-duplication.

## 3. The same spans under every strategy, on and off

Six SDT spans, top-1 concept and cosine, `allmpnet`.

### `leaves_only=True`

| span | `leaf` | `path` | `anchor` | `context` | `bracket` | `enriched` |
|---|---|---|---|---|---|---|
| intrinsic motivation | INCENTIVES 0.56 | INCENTIVES 0.72 | INCENTIVES 0.62 | INCENTIVES 0.62 | INCENTIVES 0.70 | INCENTIVES 0.65 |
| well-being | MENTAL HEALTH 0.70 | HAPPINESS 0.66 | HAPPINESS 0.63 | HAPPINESS 0.55 | HAPPINESS 0.70 | HAPPINESS 0.55 |
| autonomy support | AUTONOMY AT WORK 0.72 | AUTONOMY AT WORK 0.59 | AUTONOMY AT WORK 0.67 | AUTONOMY AT WORK 0.65 | AUTONOMY AT WORK 0.65 | AUTONOMY AT WORK 0.57 |
| self-confidence | SELF-ESTEEM 0.79 | SELF-ESTEEM 0.57 | SELF-ESTEEM 0.60 | SELF-ESTEEM 0.56 | SELF-ESTEEM 0.63 | SELF-ESTEEM 0.58 |
| need frustration | ANGER 0.55 | SATISFACTION 0.54 | BOREDOM 0.50 | SATISFACTION 0.54 | BOREDOM 0.56 | SATISFACTION 0.50 |
| academic achievement | ACADEMIC ACHIEVEMENT 1.00 | ACADEMIC ACHIEVEMENT 0.83 | ACADEMIC ACHIEVEMENT 0.82 | ACADEMIC ACHIEVEMENT 0.80 | ACADEMIC ACHIEVEMENT 0.90 | ACADEMIC ACHIEVEMENT 0.69 |

### `leaves_only=False`

| span | `leaf` | `path` | `anchor` | `context` | `bracket` | `enriched` |
|---|---|---|---|---|---|---|
| intrinsic motivation | **MOTIVATION** 0.77 | **MOTIVATION** 0.77 | **MOTIVATION** 0.73 | **MOTIVATION** 0.77 | **MOTIVATION** 0.77 | **MOTIVATION** 0.69 |
| well-being | **WELL-BEING (HEALTH)** 0.82 | **WELL-BEING (HEALTH)** 0.82 | WELL-BEING (SOCIETY) 0.70 | **WELL-BEING (HEALTH)** 0.82 | **WELL-BEING (HEALTH)** 0.82 | **WELL-BEING (HEALTH)** 0.61 |
| autonomy support | AUTONOMY AT WORK 0.72 | AUTONOMY AT WORK 0.59 | AUTONOMY AT WORK 0.67 | AUTONOMY AT WORK 0.65 | AUTONOMY AT WORK 0.65 | AUTONOMY AT WORK 0.57 |
| self-confidence | SELF-ESTEEM 0.79 | SELF-ESTEEM 0.57 | SELF-ESTEEM 0.60 | SELF-ESTEEM 0.56 | SELF-ESTEEM 0.63 | SELF-ESTEEM 0.58 |
| need frustration | ANGER 0.55 | SATISFACTION 0.54 | BOREDOM 0.50 | SATISFACTION 0.54 | BOREDOM 0.56 | SATISFACTION 0.50 |
| academic achievement | ACADEMIC ACHIEVEMENT 1.00 | ACADEMIC ACHIEVEMENT 0.83 | ACADEMIC ACHIEVEMENT 0.82 | ACADEMIC ACHIEVEMENT 0.80 | ACADEMIC ACHIEVEMENT 0.90 | ACADEMIC ACHIEVEMENT 0.69 |

How to read the two tables:

- **Rows 3 to 6 are identical on and off.** When the right concept is already a leaf, the
  switch does nothing. The only change in the candidate list is the addition of branches,
  and none of them beats the leaf for these spans.
- **Rows 1 and 2 change under every strategy.** *intrinsic motivation* moves from
  INCENTIVES (a child, and the wrong child: incentives are external rewards) to MOTIVATION.
  *well-being* moves from HAPPINESS or MENTAL HEALTH to WELL-BEING (HEALTH). Both targets are
  top concepts that leaves-only cannot offer. The scores rise too (0.65 → 0.69, 0.55 → 0.61
  under `enriched`), which says the branch is a closer match, not only a permitted one.
- **The strategy decides the score, not the concept.** Down a column the winner rarely
  changes; the cosine does. `leaf` gives the highest cosines for exact and near-exact labels
  (`academic achievement` 1.00, `self-confidence` 0.79 through the synonym in the label space).
  `enriched` gives the lowest, because its long text spreads the vector over synonyms and
  ancestors. This matters for τ: a threshold tuned for `leaf` is too strict for `enriched`.
- **`need frustration` fails everywhere.** ANGER, BOREDOM, SATISFACTION at 0.50–0.56. ELSST
  has no concept for it. No strategy and no switch invents one; this is the
  standardisation-failure class.
- **One warning in the `anchor` column.** *well-being* → WELL-BEING (SOCIETY) instead of
  WELL-BEING (HEALTH). The two top concepts have the same name apart from the bracket; the
  `anchor` recipe repeats a top concept's label twice, which shifts its vector enough to flip
  the tie. A recipe artefact, not a signal.

## 4. Which strategy, with the switch on or off

From the entry-term test in section 5 (positive and negative pairs, three
models, both settings, plus a held-out synonym test):

- The ranking of strategies is the **same on and off**: `leaf` ≥ `enriched` > `anchor` >
  `context` ≈ `bracket` > `path`. Turning the switch off moves every F1 by at most 0.01.
- `enriched` stays the default. On held-out synonyms it is never worse than `leaf` beyond
  noise and has the best hit@5; on real spans, which are paraphrases rather than labels, the
  synonyms are the part that helps.
- `path` is the weakest under both settings. Ancestors written as a chain dilute the label.
- The switch is a **granularity** choice, not an accuracy one: off, broad constructs get
  their own concept and the graph carries nodes at mixed depth; on, every node is a leaf and
  broad constructs are pushed onto a child.

## 5. The entry-term test: how the defaults were chosen

A thesaurus lists its own synonyms. ELSST gives them as `skos:altLabel`. Each synonym with
its concept is a **positive pair**: *self-confidence* ↔ SELF-ESTEEM. For each positive pair
the test adds two **negative pairs** with the same query: a **sibling** concept (same nearest
parent; hard) and a **random** concept (easy). A fixed seed draws the negatives once. A
setting scores a pair by the cosine between the query and the concept text. The rule is *same
concept if score ≥ τ*. A sweep over τ gives the best F1 and its τ. AUC is the threshold-free
view. Top-1 accuracy asks if the gold concept wins the ranking against the whole thesaurus.

ELSST, three scopes:

| scope | candidates | queries | pairs | reads as |
|---|---|---|---|---|
| leaves | 2,417 leaves | synonyms of leaves | 5,532 | `leaves_only=True` |
| all | 3,436 concepts | synonyms of all concepts | 7,888 | `leaves_only=False` |
| all·leafq | 3,436 concepts | synonyms of leaves | 5,584 | the cost of the extra candidates on the same queries |

`enriched` puts the synonyms inside the concept text. On this test the query sits inside its
own target, and the score is inflated (F1 0.84–0.92). `enriched_noalt` (label, note, path; no
synonyms) is the fair version. Best F1, fair rows, scope leaves / all:

| strategy | allmpnet | bge_base | minilm |
|---|---|---|---|
| `leaf` | 0.79 / 0.80 | **0.82 / 0.82** | 0.78 / 0.79 |
| `enriched_noalt` | 0.78 / 0.78 | 0.79 / 0.79 | 0.76 / 0.76 |
| `anchor` | 0.77 / 0.78 | 0.79 / 0.79 | 0.75 / 0.76 |
| `context` | 0.77 / 0.78 | 0.77 / 0.77 | 0.75 / 0.76 |
| `bracket` | 0.76 / 0.77 | 0.79 / 0.79 | 0.74 / 0.75 |
| `path` | 0.75 / 0.75 | 0.79 / 0.79 | 0.73 / 0.73 |

- **Strategy.** The bare label wins. Each phrasing of the tree and the note pull the vector
  away from the label and cost 0.02–0.05 F1. The spread between strategies is small next to
  the spread between models.
- **Model.** `bge_base` beats `allmpnet` by about 0.02 F1 and 0.04 top-1 accuracy in every
  cell. `minilm` is last. `bge_base` separates positives from siblings more sharply: τ* is
  0.65–0.70, against 0.45–0.55 for `allmpnet`.
- **`leaves_only`.** The branches as candidates cost F1 0.005 and top-1 accuracy 0.03–0.07 on
  the same queries. The branches bring their own labels and synonyms in return. The switch is
  a granularity choice, not an accuracy choice.
- **τ.** τ* depends on the model: about 0.50 for `allmpnet` with `leaf`, about 0.70 for
  `bge_base`. The old τ = 0.55 was set for `all-mpnet-base-v2`. Do not reuse it for another
  model, another strategy or another thesaurus.
- **The hard errors are the thesaurus's own granularity.** Siblings accepted at τ*: *sporting
  activities* → SPORTS CLUBS (gold SPORTS); *distance courses* → ONLINE EDUCATION (gold
  DISTANCE EDUCATION); *achievement tests* → INTELLIGENCE TESTS (gold EDUCATIONAL TESTS).
  Positives missed: *mores* → CUSTOMS AND TRADITIONS (0.45); *perks* → FRINGE BENEFITS (0.63).
  No setting resolves these. They are the granularity-mismatch class of the disagreement
  classifier.

**Do the synonyms in `enriched` help with a synonym the text has never seen?** A second test
holds one out. For the 651 ELSST concepts with two or more synonyms, one synonym leaves the
concept text and becomes the query. Mean F1 over three models and two scopes:

| concept text | F1 | hit@5 |
|---|---|---|
| label + remaining synonyms | 0.811 | 0.806 |
| `enriched`: label + synonyms + note + path | 0.806 | 0.821 |
| `leaf` | 0.799 | 0.796 |
| label + note + path, no synonyms | 0.779 | 0.766 |

The synonyms generalise. They add 0.01–0.03 F1 over the bare label for `bge_base` and
`minilm`, and nothing for `allmpnet`. The note and the path cost about 0.02 alone. The
synonyms pay that cost back. `enriched` stays the default: it is never worse than `leaf`
beyond noise, it gives the best hit@5, and it is the recipe Paper 3 ships.

The test itself was a temporary script and is not part of the package.

## 6. Where to look in the code

- Recipes: `strategy_text` in `theoryminer/harmonizer/taxonomy.py`.
- Entries and paths: `_load_elsst` and its inner `paths_to_root` in the same file. All
  root-to-concept paths are kept, one entry each; nothing is chosen by depth.
- The switch: `load_taxonomy(name, leaves_only)`; the cache key includes it.
- Lookup and de-duplication by concept: `_top_matches` in `standardize.py`.
