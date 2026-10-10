# Find causal claims

`causenet()` finds the cause → effect pairs in the sentences.

```python
from theoryminer import harvest, causenet

data = harvest("sample_files")
relations = causenet(data["sentences"])
```

The model `rasoultilburg/SocioCausaNet` reads one sentence at a time. It decides whether the
sentence is causal, marks the cause spans and the effect spans, and links each cause to each effect.
One sentence can give more than one relation.

## A relation

| Key | Meaning |
|---|---|
| `rel_id` | a unique id: the `sent_id` plus `r` and a number, for example `d000p0012s003r01` |
| `sent_id`, `doc_id`, `page` | from the sentence |
| `cause` | the cause span, in lowercase |
| `effect` | the effect span, in lowercase |
| `sentence` | the clean sentence |
| `doi`, `title` | the paper, from `harvest()` |

A span is the words of the sentence, as the author wrote them. The function repairs the spaces that
the tokenizer changes, and it removes no word. On the sample papers, 97 % of the relations have
both spans word for word in their sentence.

You can also give a plain list of strings. Then `doc_id` is `"input"` and `page` is 0.

## Settings

| Setting | Default | What it does |
|---|---|---|
| `threshold` | `0.8` | the score that a pair needs. A lower value gives more relations and more errors. |
| `decision` | `"span_only"` | a sentence is causal when it has a cause span and an effect span. `"cls+span"` also needs the sentence classifier (the default before 0.2.0). `"cls_only"` uses only the classifier. |
| `mode` | `"neural"` | the model scores every cause → effect pair. `"auto"` keeps every pair without a score when a sentence has only one cause or only one effect. |
| `avoid_ambiguous` | `True` | skips a relation whose span only points to another sentence, such as "this" or "it". The summary prints how many it skipped. |
| `device` | `"auto"` | an NVIDIA GPU, else the Apple GPU, else the CPU |
| `batch_size` | `64` | sentences per step. Use a smaller number when the memory of the GPU is too small. |

## Speed

| Run | Sentences | Time on a laptop CPU |
|---|---|---|
| the 7 sample papers | 2,531 | about 2 minutes |
| one snowball round, 14 papers | 4,450 | about 4 minutes |

A GPU is much faster. In Google Colab, choose a GPU runtime. The function writes no file, so keep the
result in a variable. To keep it for a later session, save it as JSON:

```python
import json

with open("outputs/relations.json", "w", encoding="utf-8") as fh:
    json.dump(relations, fh)
```

## Leave out the flagged sentences

`harvest()` flags doubtful sentences but keeps them. To keep them away from the model:

```python
sentences = [s for s in data["sentences"] if not s["flag"]]
relations = causenet(sentences)
```

See every setting in the [reference of `causenet()`](../reference/causenet.md).
