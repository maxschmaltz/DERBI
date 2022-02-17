import subprocess
import sys
# # pip install GitPython
# subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'GitPython'])
# # pip install -U spacy
# subprocess.check_call([sys.executable, '-m', 'pip', 'install', '-U', 'spacy'])
# # installing pipelines
# subprocess.check_call([sys.executable, '-m', 'spacy', 'download', 'de_core_news_lg'])
# subprocess.check_call([sys.executable, '-m', 'spacy', 'download', 'de_core_news_sm'])
# subprocess.check_call([sys.executable, '-m', 'spacy', 'download', 'de_core_news_md'])

import spacy
# we will evaluate DERBI 
# based on the following pipelines:
nlp_lg = spacy.load('de_core_news_lg')
nlp_sm = spacy.load('de_core_news_sm')
nlp_md = spacy.load('de_core_news_md')

# import DERBI
from git import Repo
Repo.clone_from('https://github.com/maxschmaltz/DERBI', 'DERBI')
from DERBI.derbi import DERBI

from DERBI.Tools import split_tags

# import requred packages
from tqdm import tqdm
from numpy import floor
import re
# we will ignore warnings
import warnings
warnings.simplefilter('ignore')

from collections import defaultdict

'''
For evaluation we use 'de_lit-ud-test.txt' from 
Universal Dependencies German HDT threebank: 
https://universaldependencies.org/treebanks/de_lit/index.html.
Unfortunately, we cannot download it from UD GitHub, as there are
only threebanks in .conllu format (we need .txt).
Treebanks can be downloaded at: https://lindat.mff.cuni.cz/repository/xmlui/handle/11234/1-4611.
'''

class DerbiTest:

    def __init__(self, model):
        self.model = model
        self.derbi = DERBI(model)

    # assert declination to ADJ (naive way)
    def update_for_ADJ(self, morph: dict, doc: spacy.tokens.Doc, ind: int) -> dict:
        if ind == 0:
            return morph

        if (doc[ind - 1].pos_ == 'ADJ') and (ind >= 2):
            if morph.get('Number') == ['Sing']:
                if (re.search('^dies|^jen|^welch', doc[ind - 2].lemma_) is not None) or (doc[ind - 2].morph.get('Definite') == ['Def']) or ((doc[ind - 2].pos_ == 'ADV') and (doc[ind - 2].morph is not None)):
                    morph['Declination'] = 'Weak'
                if (re.search('^kein', doc[ind - 2].lemma_) is not None) or (doc[ind - 2].morph.get('Poss') == ['Yes']) or (doc[ind - 2].morph.get('Definite') == ['Ind']):
                    morph['Declination'] = 'Mixed'
                else:
                    morph['Declination'] = 'Strong'
            else:
                if (doc[ind - 2].morph.get('Definite') == ['Def']) or (re.search('^dies|^jen|^welch|^all|^beid|^kein', doc[ind - 2].lemma_) is not None) or (doc[ind - 2].morph.get('Poss') == ['Yes']):
                    morph['Declination'] = 'Weak'
                else:
                    morph['Declination'] = 'Strong'

        else:
        
            if morph.get('Number') == ['Sing']:
                if (re.search('^dies|^jen|^welch', doc[ind - 1].lemma_) is not None) or (doc[ind - 1].morph.get('Definite') == ['Def']) or ((doc[ind - 1].pos_ == 'ADV') and (doc[ind - 1].morph is not None)):
                    morph['Declination'] = 'Weak'
                if (re.search('^kein', doc[ind - 1].lemma_) is not None) or (doc[ind - 1].morph.get('Poss') == ['Yes']) or (doc[ind - 1].morph.get('Definite') == ['Ind']):
                    morph['Declination'] = 'Mixed'
                else:
                    morph['Declination'] = 'Strong'
            else:
                if (doc[ind - 1].morph.get('Definite') == ['Def']) or (re.search('^dies|^jen|^welch|^all|^beid|^kein', doc[ind - 1].lemma_) is not None) or (doc[ind - 1].morph.get('Poss') == ['Yes']):
                    morph['Declination'] = 'Weak'
                else:
                    morph['Declination'] = 'Strong'

        return morph

    # call with DERBI with Poss DET stem, not lemma, as spaCy has lemma 'mein(en)' for all
    # posessive DETs but gives no possibility to assert person explicitly
    def assert_lemma_poss_DET(self, token: spacy.tokens.token.Token) -> spacy.tokens.token.Token:
        euer_pattern = re.compile('eue{0,1}r')
        poss_pattern = re.compile('[dms]ein|unser|ihr')

        if euer_pattern.search(token.text.lower()) is not None:
            token.lemma_ = 'euer'
        elif poss_pattern.search(token.text.lower()) is not None:
            token.lemma_ = poss_pattern.search(token.text.lower())[0]
        
        return token

    '''
    We want to make a window test:
    we shift a window, containing one target token.
    The window is necessary for spaCy to understand the context.
    For each target we call DERBI with target.lemma_ but with target.morph tags
    to see if DERBI could restore it.

    Example of test data (answer, DERBI input, DERBI input target index, DERBI input target features):

        text = 'Juliana kommt aus Paris. Das ist die Hauptstadt von Frankreich.'
        get_test_data(nlp, text):

        [('juliana kommt aus paris .', 'juliana kommt aus paris .', 0, {'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing'}),
        ('juliana kommt aus paris .', 'juliana kommen aus paris .', 1, {'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Tense': 'Pres', 'VerbForm': 'Fin'}),
        ('juliana kommt aus paris .', 'juliana kommt aus paris .', 2, {}),
        ('kommt aus paris . das', 'kommt aus paris . das', 2, {'Case': 'Dat', 'Gender': 'Neut', 'Number': 'Sing'}),
        ('paris . das ist die', 'paris . der ist die', 2, {'Case': 'Nom', 'Gender': 'Neut', 'Number': 'Sing', 'PronType': 'Dem'}),
        ('. das ist die hauptstadt', '. das sein die hauptstadt', 2, {'Mood': 'Ind', 'Number': 'Sing', 'Person': '3', 'Tense': 'Pres', 'VerbForm': 'Fin'}),
        ('das ist die hauptstadt von', 'das ist der hauptstadt von', 2, {'Case': 'Nom', 'Definite': 'Def', 'Gender': 'Fem', 'Number': 'Sing', 'PronType': 'Art'}),
        ('ist die hauptstadt von frankreich', 'ist die hauptstadt von frankreich', 2, {'Case': 'Nom', 'Gender': 'Fem', 'Number': 'Sing'}),
        ('die hauptstadt von frankreich .', 'die hauptstadt von frankreich .', 2, {}),
        ('die hauptstadt von frankreich .', 'die hauptstadt von frankreich .', 3, {'Case': 'Dat', 'Gender': 'Neut', 'Number': 'Sing'})]
    '''
    def get_test_data(self, model: spacy.lang.de.German, text: str, n_window: int=5) -> list:
        german_abc_ext = re.compile('[^a-zäöüß]')
        test_data = []

        text = text.lower()
        doc = model(text)
        N = len(doc)
        for i, target in enumerate(doc):
            if german_abc_ext.search(target.text.lower()) is not None:
                continue

            begin = int(i - floor(n_window / 2)) if i - floor(n_window / 2) >= 0 else 0
            if begin + n_window <= N:
                end = begin + n_window
            else:
                begin, end = N - n_window, N

            morph = split_tags(str(target.morph))
            # define ADJ declination
            if target.pos_ == 'ADJ':
                morph = self.update_for_ADJ(morph, doc[begin: end], i - begin)
            # call with stem, not lemma, as spaCy has lemma 'mein(en)' for all
            # posessive DETs but gives no possibility to assert person explicitly
            if (target.pos_ == 'DET') and ('Poss=Yes' in str(target.morph)):
                target = self.assert_lemma_poss_DET(target)

            window = ' '.join([t.lemma_ if j == (i - begin) else t.text.lower() 
                              for j, t in enumerate(doc[begin: end])])
            ans = target.text.lower()

            test_data.append((ans, window, i - begin, morph, target.pos_))
        
        return test_data

    def test(self, test_data: list) -> dict:
        self.exceptions = defaultdict(list)
        success = {}
        for ans, window, ind, tags_dict, pos in tqdm(test_data):
            '''
            we pass Exceptions as almost all of them 
            are consequenses of spaCy confusions leading
            to conflict with LabelScheme
            (e.g., spaCy othen confuses ADV and ADJ; the 
            significant part of error refer to that ADV cannot
            have Case, Gender, ...)
            '''
            try:
                _ = self.derbi(window, tags_dict, ind)
                pred = self.derbi.to_inflect[str(ind)].get('result')
            except Exception as e:
                self.exceptions[type(e).__name__].append(e)
                continue

            if success.get(pos) is None:
                    success[pos] = [0, 0, 0]

            # for us to be independent from 
            # count of whitespaces
            if pred.strip() == ans.strip():
                success[pos][0] += 1
            success[pos][1] += 1
        
        return {
            'summary': (sum([s[0] for s in success.values()]), sum([s[1] for s in success.values()]), 
                        round(sum([s[0] for s in success.values()]) / sum([s[1] for s in success.values()]), 3)),
            'scores': {k: (s[0], s[1], round(s[0] / s[1], 3)) for k, s in success.items()}
            }

    def __call__(self, text_path: str) -> dict:
        with open(text_path) as test_file:
            test_text = test_file.read().replace('\n', ' ')

        test_data = self.get_test_data(self.model, test_text)
        self.scores = self.test(test_data)
        return self.scores

    
def main():
    path = 'DERBI/test/UDGermanTreebanks/de_lit-ud-test.txt'

    test_lg = DerbiTest(nlp_lg)
    test_sm = DerbiTest(nlp_sm)
    test_md = DerbiTest(nlp_md)

    print('de_core_news_lg...', end='\n\n')
    print(test_lg(path))
    for key, exc in test_lg.exceptions.items():
        print(key, len(exc))
    print('\n\n\n')
    print('de_core_news_sm...', end='\n\n')
    print(test_sm(path))
    for key, exc in test_sm.exceptions.items():
        print(key, len(exc))
    print('\n\n\n')
    print('de_core_news_md...', end='\n\n')
    print(test_md(path))
    for key, exc in test_md.exceptions.items():
        print(key, len(exc))

if __name__ == '__main__':
    main()


# de_core_news_lg...

# 100%|██████████| 34813/34813 [03:32<00:00, 163.97it/s]
# {'summary': (29685, 31240, 0.95), 'scores': {'PRON': (2750, 2964, 0.928), 'VERB': (2539, 3081, 0.824), 'DET': (4947, 5009, 0.988), 'NOUN': (6315, 6564, 0.962), 'ADV': (4190, 4327, 0.968), 'AUX': (1734, 1901, 0.912), 'ADP': (2801, 2807, 0.998), 'CCONJ': (1658, 1658, 1.0), 'SCONJ': (709, 712, 0.996), 'PROPN': (337, 368, 0.916), 'ADJ': (745, 886, 0.841), 'X': (51, 51, 1.0), 'NUM': (32, 35, 0.914), 'PART': (876, 876, 1.0), 'INTJ': (1, 1, 1.0)}}
# ValueError 3393
# AttributeError 180


# de_core_news_sm...

# 100%|██████████| 34813/34813 [03:15<00:00, 178.51it/s]
# {'summary': (29256, 30831, 0.949), 'scores': {'PRON': (2767, 2980, 0.929), 'VERB': (2496, 3152, 0.792), 'DET': (4925, 4964, 0.992), 'NOUN': (6059, 6321, 0.959), 'ADV': (4201, 4322, 0.972), 'AUX': (1805, 1959, 0.921), 'ADP': (2789, 2795, 0.998), 'CCONJ': (1659, 1659, 1.0), 'PART': (878, 878, 1.0), 'SCONJ': (714, 715, 0.999), 'PROPN': (314, 339, 0.926), 'ADJ': (539, 636, 0.847), 'X': (36, 36, 1.0), 'NUM': (74, 75, 0.987)}}
# ValueError 3509
# AttributeError 473


# de_core_news_md...

# 100%|██████████| 34813/34813 [03:32<00:00, 164.11it/s]
# {'summary': (29715, 31374, 0.947), 'scores': {'PRON': (2772, 3009, 0.921), 'VERB': (2541, 3126, 0.813), 'DET': (4939, 4999, 0.988), 'NOUN': (6235, 6506, 0.958), 'ADV': (4216, 4351, 0.969), 'AUX': (1805, 1972, 0.915), 'ADP': (2808, 2815, 0.998), 'CCONJ': (1662, 1662, 1.0), 'SCONJ': (708, 709, 0.999), 'PROPN': (351, 373, 0.941), 'ADJ': (731, 903, 0.81), 'PART': (866, 866, 1.0), 'NUM': (29, 31, 0.935), 'X': (48, 48, 1.0), 'PUNCT': (3, 3, 1.0), 'INTJ': (1, 1, 1.0)}}
# ValueError 3186
# AttributeError 253
