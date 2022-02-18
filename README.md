# DERBI: DEutscher RegelBasierter Inflektor
[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](https://www.apache.org/licenses/LICENSE-2.0)

DERBI (DEutscher RegelBasierter Inflektor) is a simple rule-based automatic inflection model for German based on [spaCy](https://spacy.io). <br> Applicable regardless of POS!

---

### Table of Contents
* [How It Works](https://github.com/maxschmaltz/DERBI/edit/main/README.md#how-it-works)
* [Installation](https://github.com/maxschmaltz/DERBI/edit/main/README.md#installation)
* [Simple Usage](https://github.com/maxschmaltz/DERBI/edit/main/README.md#simple-usage)
  * [Example](https://github.com/maxschmaltz/DERBI/blob/main/README.md#example)
  * [Arguments](https://github.com/maxschmaltz/DERBI/blob/main/README.md#arguments)
  * [Output](https://github.com/maxschmaltz/DERBI/blob/main/README.md#output)
* [Tags](https://github.com/maxschmaltz/DERBI/blob/main/README.md#tags)
* [Performance](https://github.com/maxschmaltz/DERBI/blob/main/README.md#performance)
* [License](https://github.com/maxschmaltz/DERBI/blob/main/README.md#license)

---

## How It Works

1. DERBI gets an input text;
2. The text is processes with the given spaCy model;
3. For each word to be inflected in the text:
   - The features predicted by spaCy are overridden with the input features (where specified);
   - The words with the result features come through the rules and get inflected;
4. The result is assembled into the output. 

For the arguments, see [below]((https://github.com/maxschmaltz/DERBI/blob/main/README.md#arguments)). 

## Installation

Install all necessary packages:
```python
pip install -r requirements.txt
```
Clone DERBI:
```python
git clone https://github.com/maxschmaltz/DERBI
```
or
```python
from git import Repo
Repo.clone_from('https://github.com/maxschmaltz/DERBI', 'DERBI')
```
Installation via `pip install` is not available yet. Keep an eye on the updates!

## Simple Usage
Note that DERBI works with [spaCy](https://spacy.io). Make sure to have installed any of the [spaCy pipelines for German](https://spacy.io/models/de).

### Example

```python
# python -m spacy download de_core_news_sm
nlp = spacy.load('de_core_news_md')

from DERBI.derbi import DERBI
derbi = DERBI(nlp)

derbi(
    'DERBI sein machen, damit es all Entwickler ein Mögligkeit geben, jedes deutsche Wort automatisch zu beugen',
    [{'Number': 'Sing', 'Person': '3', 'Verbform': 'Fin'},     # sein -> ist
     {'Verbform': 'Part'},                                     # machen -> gemacht
     {'Case': 'Dat', 'Number': 'Plur'},                        # all -> allen
     {'Case': 'Dat', 'Number': 'Plur'},                        # Entwickler -> entwicklern
     {'Gender': 'Fem'},                                        # ein -> eine
     {'Number': 'Sing', 'Person': '3', 'Verbform': 'Fin'},     # geben -> gibt
     {'Case': 'Acc', 'Number': 'Plur'},                        # jedes -> jede
     {'Case': 'Acc', 'Declination': 'Weak', 'Number': 'Plur'}, # deutsche -> deutschen
     {'Case': 'Acc', 'Number': 'Plur'}],                       # wort -> wörter
    [1, 2, 6, 7, 8, 10, 12, 13, 14]
)

# Output:
'derbi ist gemacht , damit es allen entwicklern eine mögligkeit gibt , jede deutschen wörter automatisch zu beugen'
```

### Arguments

#### \_\_init\_\_() Arguments
- model: _spacy.lang.de.German_
> Any of the [spaCy pipelines for German](https://spacy.io/models/de). If model is not of the type _spacy.lang.de.German_, throws an exception.

#### \_\_call\_\_() Arguments

- **text**: _str_
> Input text, containing the words to be inflected. It is strongly recommended to call DERBI with a text, not a single word, as spaCy predictions vary depending on the context.
- **target_tags**: _dict_ or _list\[dict\]_
> Dicts of category-feature values for each word to be inflected. If _None_, no inflection is implemented. Default is `None`.
> 
> NB! As the features are overriden over the ones predicted by spaCy, in `target_tags` only different ones can be specified. Note though, that spaCy predictions are not always correct, so for the DERBI output to be more precise, we recommend to specify the desired features fully. Notice also, that if no tags for an obligatory category were provided (neither by spaCy, neither in `target_tags`), DERBI restores them as default; default features values are available at [ValidFeatures](https://github.com/maxschmaltz/DERBI/blob/main/meta/ValidFeatures.json) (the first element for every category).
- **indices**: _int_ or _list\[int\]_
> Indices of the words to be inflected. Default is `0`.
>
> NB! The indices order must correspond to the target tags order. Note also, that the input text is lemmatized with the given spaCy model tokenizer, so the indices will be indexing a _spacy.tokens.Doc_ instance.

### Output
Returns _str_: the input text, where the specified words are replaced with inflection results. The output is normalized.

## Tags

DERBI uses [Universal POS tags](https://universaldependencies.org/u/pos/index.html) and [Universal Features](https://universaldependencies.org/u/feat/) (so does spaCy) with some extensions of features (not POSs). See [LabelScheme](https://github.com/maxschmaltz/DERBI/blob/main/meta/LabelsScheme.json) and [ValidFeatures](https://github.com/maxschmaltz/DERBI/blob/main/meta/ValidFeatures.json) for more details.

The following category-feature values can be used in `target-tags`: 

| **Category** (explanation) | **Valid Features** (explanation) | In Universal Features |
| :--- | :--- | :---: |
| **Case** | **Acc** (Accusative) <br> **Dat** (Dative) <br> **Gen** (Genitive) <br> **Nom** (Nominative) | **Yes** |
| **Declination** (Applicable for the words <br> with the adjective declination. <br> In German such words are declinated <br> differently depending on the left context.) | **Mixed** <br> **Strong** <br> **Weak** | **No** |
| **Definite** (Definiteness) | **Def** (Definite) <br> **Ind** (Definite) | **Yes** |
| **Degree** (Degree of comparison) | **Cmp** (Comparative) <br> **Pos** (Positive) <br> **Sup** (Superlative) | **Yes** |
| **Foreign** (Whether the word is foreign. <br> Applies to POS **X**) | **Yes** | **Yes** |
| **Gender** | **Fem** (Feminine) <br> **Masc** (Masculine) <br> **Neut** (Neutral) | **Yes** |
| **Mood** | **Imp** (Imperative) <br> **Ind** (Indicative) <br> **Sub** (Subjunctive) <br><br> NB! **Sub** is for Konjunktiv I <br> when **Tense=Pres** and for <br> Konjunktiv II when **Tense=Past**) | **Yes** |
| **Number** | **Plur** (Plural) <br> **Sing** (Singular) | **Yes** |
| **Person** | **1** <br> **2** <br> **3** | **Yes** |
| **Poss** (Whether the word is possessive. <br> Applies to pronouns and determiners.) | **Yes** | **Yes** |
| **Prontype** (Type of a pronoun, a determiner, <br> a quantifier or a pronominal adverb. | **Art** (Article) <br> **Dem** (Demonstrative) <br> **Ind** (Indefinite) <br> **Int** (Interrogative) <br> **Prs** (Personal) <br> **Rel** Relative | **Yes** |
| **Reflex** (Whether the word is reflexive. <br> Applies to pronouns and determiners.) | **Yes** | **Yes** |
| **Tense** | **Past** <br> **Pres** (Present) | **Yes** |
| **Verbform** (Form of a verb) | **Fin** (Finite) <br> **Inf** (Infinitive) <br> **Part** (Participle) <br><br> NB! **Part** is for Partizip I <br> when **Tense=Pres** and for <br> Partizip II when **Tense=Past**) | **Yes** |

Note though, that categories **Definite**, **Foreign**, **Poss**, **Prontype** and **Reflex** cannot be alternated by DERBI, and thus there is no need to specify them. 

NB! DERBI accepts capitalized tags. For example, use **Prontype**, not **PronType**. 

## Performance

#### Disclaimer
For evaluation we used [Universal Dependencies](https://universaldependencies.org) [German Treebanks](https://universaldependencies.org/de/index.html). Unfortunately, there are only `.conllu` in their GitHub repositories so we had to [download](https://universaldependencies.org/#download) some of `.txt` datasets and add it to our repository. We do not distribute these datasets though; it is your responsibility to determine whether you have permission to use them.

Evaluation conducted with dataset 'de_lit-ud-test.txt' from Universal Dependencies [German LIT threebank](https://universaldependencies.org/treebanks/de_lit/index.html) (≈31k tokens), accuracy:

| | de_core_news_md | de_core_news_sm| de_core_news_lg |
| :--- | :---: | :---: | :---: |
| Overall |   0.947 | 0.949 | 0.95  |
| **ADJ** |   0.81  | 0.847 | 0.841 |
| **ADP** |   0.998 | 0.998 | 0.998 |
| **ADV** |   0.969 | 0.972 | 0.968 |
| **AUX** |   0.915 | 0.921 | 0.912 |
| **CCONJ** | 1.0   | 1.0   | 1.0   | 
| **DET** |   0.988 | 0.992 | 0.988 |
| **INTJ** |  1.0   | 1.0   | 1.0   |
| **NOUN** |  0.958 | 0.959 | 0.962 |
| **NUM** |   0.935 | 0.987 | 0.914 |
| **PART** |  1.0   | 1.0   | 1.0   |
| **PRON** |  0.921 | 0.929 | 0.928 |
| **PROPN** | 0.941 | 0.926 | 0.916 |
| **SCONJ** | 0.999 | 0.999 | 0.996 |
| **VERB** |  0.813 | 0.792 | 0.824 |
| **X** |     1.0   | 1.0   | 1.0   |

If you are interested in the way we obtained the results, please refer to [test0.py](https://github.com/maxschmaltz/DERBI/blob/main/test/test0.py).

Or you could check it with the following code:
```python
from DERBI.test import test0
test0.main()
```

Notice that performance might vary depending on the dataset. Also remember, that if spaCy might make mistakes predicting (that means, that in some cases DERBI inflection is correct but does not correspond spaCy's tags), which also affects evaluation. 

## License

> Copyright 2022 Max Schmaltz: @maxschmaltz
> 
> Licensed under the Apache License, Version 2.0 (the "License"); <br>
> you may not use this file except in compliance with the License. <br>
> You may obtain a copy of the License at <br>
> 
>    http://www.apache.org/licenses/LICENSE-2.0 <br>
> 
> Unless required by applicable law or agreed to in writing, software <br>
> distributed under the License is distributed on an "AS IS" BASIS, <br>
> WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. <br>
> See the License for the specific language governing permissions and <br>
> limitations under the License.
