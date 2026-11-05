# Find causal claims

`causenet()` reads each sentence and finds the causal claims in it. A causal claim says that one
thing (the cause) changes another thing (the effect). For each claim, the function returns one
relation: the cause, the effect and the sentence.

For example, the sentence "Social support increases feelings of security and well-being." gives
one relation: the cause is "social support" and the effect is "feelings of security and
well-being".

A cause or an effect is a span: a part of the sentence, word for word.

The function uses the model `rasoultilburg/SocioCausaNet`. The first call downloads the model
(about 430 MB).

## An example

```python
from theoryminer import harvest, causenet

data = harvest("sample_files")

relations = causenet(
    data["sentences"],       # the sentences from harvest()
    threshold=0.8,           # the score that a cause and an effect need to make a relation
)
```

You can also give a list of your own sentences:

```python
relations = causenet(["Social support increases feelings of security and well-being."])
```

## The arguments

| Argument | What you give | Default |
|---|---|---|
| `sentences` | The sentences. Give `data["sentences"]` from `harvest()`, or a list of strings. | none; you must give it |
| `threshold` | A number from 0 to 1. The model gives a score to each cause and effect pair. A pair with a lower score gives no relation. A lower value gives more relations and more errors. | `0.8` |
| `decision` | The rule that makes a sentence causal. `"span_only"`: the model finds a cause and an effect in it. `"cls+span"`: also a second part of the model must say that the sentence is causal. This gives fewer relations. `"cls_only"`: only that second part decides. | `"span_only"` |
| `mode` | How the function joins the causes and the effects of one sentence. `"neural"`: the model scores each pair. `"auto"`: when a sentence has only one cause or only one effect, the function keeps each pair without a score. | `"neural"` |
| `avoid_ambiguous` | `True` skips a relation when its cause or effect is only a word such as "this" or "it". Such a word points to another sentence, so it has no meaning alone. | `True` |
| `device` | Where the model runs: `"auto"`, `"cpu"`, `"cuda"` (an NVIDIA GPU) or `"mps"` (an Apple Silicon Mac). `"auto"` uses a GPU when there is one. | `"auto"` |
| `batch_size` | The number of sentences that the model reads at one time. Use a smaller number when the GPU has an "out of memory" error. | `64` |

## The result

A list with one dict for each relation. One sentence can give more than one relation.

| Key | Meaning |
|---|---|
| `rel_id` | a unique id: the `sent_id` and a number, for example `d000p0012s003r01` |
| `sent_id` | the id of the sentence |
| `doc_id` | the file name of the paper, without `.pdf` |
| `page` | the page of the sentence |
| `cause` | the cause span, in lowercase |
| `effect` | the effect span, in lowercase |
| `sentence` | the full sentence |
| `doi`, `title` | the DOI and the title of the paper, or `""` |

For a list of strings, `doc_id` is `"input"` and `page` is `0`.

To see the relations as a table:

```python
import pandas as pd

table = pd.DataFrame(relations)
print(table[["cause", "effect", "sentence"]].head())
```

## How long it takes

On a laptop CPU, the 7 sample papers (2,531 sentences) take about 2 minutes. A GPU is much
faster. In Google Colab, select a GPU: Runtime → Change runtime type → T4 GPU.

The function writes no file. To use the relations in a later session, save them:

```python
import json

with open("outputs/relations.json", "w", encoding="utf-8") as fh:
    json.dump(relations, fh)
```

To load them again:

```python
with open("outputs/relations.json", encoding="utf-8") as fh:
    relations = json.load(fh)
```
