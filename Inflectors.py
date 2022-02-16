# import required modules
import json
import os
import re
# import spaCy
import spacy

# in DERBI we need a compound splitter; we use dtuggener/CharSplit.
# to access it, we first need do some manipulations:
    # clone to folder 'Charsplit'
from git import Repo
Repo.clone_from('https://github.com/dtuggener/CharSplit', 'CharSplit')
    # in folder 'Charsplit' create an empty file '__init__.py' 
    # for python to recognize the folder as a package
filepath = os.path.join('CharSplit', '__init__.py')
with open(filepath, 'w') as i:
    i.write('')
    # in file 'Charsplit/charsplit/__init__.py' we delete all the text
    # as running it, python throws an exception
filepath = os.path.join('CharSplit/charsplit', '__init__.py')
with open(filepath, 'w') as i:
    i.write('')
    # finally import
from CharSplit.charsplit.splitter import Splitter
splitter = Splitter()

# import required scripts
from DERBI import Tools

'''
For each POS we have its own inflector (the list of correspondance can be found at
https://github.com/maxschmaltz/DERBI/blob/main/Router.json).
Each one is organized generally the same way though:
    1. Search in lexicon. 
        If the desired form of the input token is 
        some kind of exception, it will be obtained via lexicon.
        The common way is full inflection (all the word);
        but in some cases only stem can be alternated and the flexion
        is obtained correspondingly to the regular model.
    2. Apply regular model.
        After the input has gone through the lexicon, the output is
        either returned or inflected with the regular model.
'''
# Basic Parent Class
class BasicInflector:

    def __init__(self, fa_path: str=None, lexc_path: str=None):
        self.auto_rules, self.lexc_rules = None, None
        # obtain rules
        if fa_path is not None:
            self.auto_rules = Tools.StateMachine(fa_path).rules
        if lexc_path is not None:
            self.lexc_rules = Tools.Lexicon(lexc_path).rules

    def search_in_lexicon(self, lemma: str, target_tags: str) -> tuple:
        if (self.lexc_rules is None) or (self.lexc_rules.get(lemma) is None):
            return lemma, Tools.split_tags(target_tags)
        else:
            tags_dict = Tools.split_tags(target_tags)
            curr_rules = self.lexc_rules[lemma]
            for rule in curr_rules:
                # we require partial match
                rule_is_applicable = set([((rule['rule'].get(cat) is None) or (feat in rule['rule'][cat])) 
                                      for cat, feat in tags_dict.items()]) == {True}
                if rule_is_applicable:
                    # we return output and the not matched features (for further inflection) as well  
                    return rule['output'], {cat: feat for cat, feat in tags_dict.items() if rule['rule'].get(cat) is None}
            else:
                return lemma, Tools.split_tags(target_tags)

    def automata(self, token: str, tags_dict: dict) -> str:
        if self.auto_rules is None:
            return token

        for rule in self.auto_rules:
            # here we require full match though
            rule_is_applicable = (set([tags_dict.get(cat, '') in rule['rule'][cat]  
                                  for cat, feat in rule['rule'].items()]) == {True}) or (rule['rule'] == {})
            if rule_is_applicable:
                token = re.sub(rule['pattern'], rule['to_sub'], token)
            # print(rule, token)
        return token

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        # the common way:
            # 1. search in lexicon
        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output
            # 2. apply regular model
        return self.automata(output, remaining_tags)


# CCONJ, INTJ, NUM, PART, SCONJ, X
class Uninflected(BasicInflector):

    def search_in_lexicon(self, *args):
        pass

    def automata(self, *args):
        pass

    # drop tags
    def __call__(self, token: spacy.tokens.token.Token, _):
        return token.norm_


# ADJ, ADV
class ADJInflector(BasicInflector):
    
    # most of the one syllable ADJ and ADV
    # toss an umlaut in comparative and superlative,
    # e.g. groß -> größer
    def umlaut(self, token: str) -> str:
        if token.count('#') != 1:
            return token.replace('#', '')
        token = re.sub('#a', 'ä', token)
        token = re.sub('#o', 'ö', token)
        token = re.sub('#u', 'ü', token)
        # if not applicable, there is no umlaut
        return token.replace('#', '')

    def __call__(self, token: spacy.tokens.token.Token or str, target_tags: str) -> str:
        # from AUX and VERB we can receive <str> tokens
        # (when Verbform=Part),
        # so we must just pass the following part then
        if not isinstance(token, str):
            # somehow for ADV and ADJ spacy add 'en' to lemma in Degree=Pos,
            # e.g. 'schnell'.lemma_ = 'schnellen' but 'schneller'.lemma_ = 'schnell'
            if (token.pos_ == 'ADV') and (token.text.lower() + 'en' == token.lemma_):
                token.lemma_ = token.text
            # somehow for ADV spacy add 'e'/'en'/... to lemma in some forms,
            # e.g. 'rote'.lemma_ = 'rote' but 'roten'.lemma_ = 'rot' 
            if (token.pos_ == 'ADJ') and (token.text.lower() == token.lemma_) and (len(Tools.split_tags(target_tags)) > 1):
                token.lemma_ = re.sub('e[mnrs]{0,1}$', '', token.lemma_)

            output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
            if not(len(remaining_tags)):
                return output
        else:
            output = token
            remaining_tags = Tools.split_tags(target_tags)
            
        auto_output = self.automata(output, remaining_tags)
        # toss an umlaut, if applicable
        return self.umlaut(auto_output)


# ADP
class ADPInflector(BasicInflector):

    def automata(self, *args):
        pass
    
    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output
        
        # if an adposition came through the lexc and returned with
        # remaining tags, it means it's not there (as APD.lexc defines 
        # all the features); then we're trying to inflect the adp to 
        # a form it can't have
        raise ValueError('Features "' + target_tags + 
                            '" are not available for word "' + token.norm_ + '".')


# AUX
class AUXInflector(BasicInflector):

    def __init__(self, fa_path: str=None, lexc_path: str=None):
        super().__init__(fa_path, lexc_path)
        # ADJInflector for participles
        self.adj_inflector = ADJInflector('DERBI/meta/automata/ADJ.fa')

    # strong german verbs toss an umlaut
    # when Mood=Sub, 
    # e.g. war -> wäre
    def umlaut(self, token: str) -> str:
        if '&' not in token:
            return token

        past_stem = token[:token.index('&')]
        sub_stem = re.sub('a', 'ä', past_stem)
        sub_stem = re.sub('o', 'ö', sub_stem)
        sub_stem = re.sub('u', 'ü', sub_stem)
        return re.sub('^' + past_stem + '&', sub_stem, token)

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str):
        # restrict imperative forms formation for modal verbs
        if ((token.lemma_.lower() in ['dürfen', 'können', 'mögen', 'müssen', 'sollen', 'wollen'])
                                                                and ('Mood=Imp' in target_tags)):
            raise ValueError('No Imperative forms available for modal verbs.')
            
        if token.lemma_ == 'habe':
            token.lemma_ = 'haben'

        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output

        output = self.automata(output, remaining_tags)
        # toss an umlaut if applicable
        output = self.umlaut(output)

        # use ADJInflector for participles,
        # as they inflect the same way
        if 'Verbform=Part' in target_tags:
            return self.adj_inflector(output, target_tags + '|Degree=Pos')
        
        return output


# DET
class DETInflector(BasicInflector):

    def parse_poss_dets(self, token: str) -> str:
        # 'euer' is distinct, as it has a prothetical vowel
        euer_pattern = re.compile('eue{0,1}r')
        poss_pattern = re.compile('[dms]ein|unser|ihr')

        if euer_pattern.search(token) is not None:
            match = 'euer'
        elif poss_pattern.search(token) is not None:
            match = poss_pattern.search(token)[0]
        else:
            match = 'mein'

        return match

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        # restrict plural forms formations for 'ein'
        if (re.search('^ein(e[mnrs]{0,1}){0,1}', token.lemma_.lower()) is not None) and ('Number=Plur' in target_tags):
            raise ValueError('Article "ein" has only Singular forms.')
        
        # detect possessive pronouns
        input = token.lemma_.lower() if 'Poss=Yes' not in target_tags else self.parse_poss_dets(token.text.lower())

        output, remaining_tags = self.search_in_lexicon(input, target_tags)
        if not(len(remaining_tags)):
            return output

        return self.automata(output, remaining_tags)


# NOUN
class NOUNInflector(BasicInflector):

    def __init__(self, fa_path: str=None, lexc_path: str=None):
        super().__init__(fa_path, lexc_path)
        # ADJInflector for nouns of adjective declination
        self.adj_inflector = ADJInflector('DERBI/meta/automata/ADJ.fa')

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:        
        # adjective declination nouns
        if 'Declination=' in target_tags:
            if re.search('e[mnrs]{0,1}$', token.norm_) is None:
                raise ValueError('Could not decline word "' + token.norm_ + '" as an ADJ.')
            token.lemma_ = re.sub('e[mnrs]{0,1}$', '', token.lemma_.lower())
            return self.adj_inflector(token, target_tags + '|Degree=Pos')

        # primary search in lexicon      
        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output

        # if fails, we'll try to split it and search once again
        splitted = splitter.split_compound(output)[0]
        # it's no compound then
        if splitted[0] == 0:
            return self.automata(output, remaining_tags)

        splitted = splitted[1:]
        # search once again, now the compound head
        output, remaining_tags = self.search_in_lexicon(splitted[1].lower(), target_tags)
        if not(len(remaining_tags)):
            return output
        
        # restore compound
        return splitted[0].lower() + self.automata(output, remaining_tags)


# PRON
class PRONInflector(BasicInflector):

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        # we need it for the state machine not to be confused,
        # as every reflexive pronoun has tag 'Reflex=Yes' and PronType=Prs;
        # we need only Reflex=Yes
        if 'Reflex=Yes' in target_tags:
            target_tags = target_tags.replace('Prontype=Prs|', '')

        # assert lemma 'ich' for personal pronouns
        # (for some reason lemmas for them vary)
        if 'Prontype=Prs' in target_tags:
            token.lemma_ = 'ich'

        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output
        
        return self.automata(output, remaining_tags)


# PROPN
class PROPNInflector(BasicInflector):

    def search_in_lexicon(self, *args):
        pass

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        tags_dict = Tools.split_tags(target_tags)
        return self.automata(token.lemma_.lower(), tags_dict)


# VERB
class VERBInflector(AUXInflector):

    def __init__(self, fa_path: str=None, lexc_path: str=None):
        super().__init__(fa_path, lexc_path)
        # we need to distinct between separable and inseparable prefixes
        with open('DERBI/meta/lexicons/verb_prefixes.json') as j:
            self.prefixes = json.load(j)

    # split a verb into prefixes and non-prefix-part
    def sep_prefixes(self, token: str) -> str:
        # first we have to separate the flexion
        stem = re.sub('(en$|(?<=[lr])n$|(?<=tu)n$|(?<=sei)n$)', '', token)
        # second we want to substitude all the diphthongs with one-symbol characters
        # to know exactly the count of syllables (for the function
        # not to separate the prefix leaving 'syllableless' stem)
        dis = {
            'ei': 'E',
            'ie': 'I',
            'eu': 'U',
            'äu': 'Y'
        }
        di_pattern = re.compile('(ei|ie|eu|äu)')
        while di_pattern.search(stem) is not None:
            di = di_pattern.search(stem)[0]
            stem = re.sub(di, dis[di], stem)

        syls = lambda x: len(re.findall('[aeiouyäöüEIUY]', x))
        
        prefs = []
        # detect and separate prefixes
        prefixes_pattern = re.compile('^' + '|^'.join(self.prefixes['sep'] + self.prefixes['insep']))
        while prefixes_pattern.search(stem) is not None:
            pref = prefixes_pattern.search(stem)[0]
            if syls(re.sub(pref, '', stem)) == 0:
                break
            prefs.append(pref)
            stem = re.sub(pref, '', stem, count=1)

        if not len(prefs):
            return ('', False, token)
        
        # restore diphthongs
        restore_dis = lambda x, matches: x if not len(matches) else restore_dis(re.sub(matches[-1], 
                                    {v: k for k, v in dis.items()}[matches[-1]], x), matches[:-1])
        # we also need to know if the prefix complex is separable or inseparable
        insep = ((prefs[0] in self.prefixes['insep']) or (prefs[-1] in self.prefixes['insep']))
        prefs = restore_dis(''.join(prefs), re.findall('|'.join({v: k for k, v in dis.items()}.keys()), ''.join(prefs)))
        return prefs, insep, re.sub('^' + prefs, '', token)

    # restore separated prefixes
    def add_prefixes(self, prefixes: str, insep: bool, token: str, separate: bool) -> str:
        if not len(prefixes):
            return re.sub('#', 'ge', token)
        # separable prefixes are joint at the beginning anyways
        if insep:
            return prefixes + re.sub('#', '', token)
        # inseparable prefixes are separated in finite and imperative forms
        if separate:
            return '(' + token + ' , ' + prefixes + ') '
        # inseparable prefixes are joint in participles
        return prefixes + re.sub('#', 'ge', token)

    def __call__(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        # restrict imperative forms formation for modal verbs
        if ((token.lemma_.lower() in ['dürfen', 'können', 'mögen', 'müssen', 'sollen', 'wollen'])
                                                                and ('Mood=Imp' in target_tags)):
            raise ValueError('No Imperative forms available for modal verbs.')
        
        if token.lemma_ == 'habe':
            token.lemma_ = 'haben'
        
        # separate prefixes
        prefixes, insep, stem = self.sep_prefixes(token.lemma_.lower())

        # NB! in lexicon we search only non-prefix part
        output, remaining_tags = self.search_in_lexicon(stem, target_tags)
        if not(len(remaining_tags)):
            return output

        output = self.automata(output, remaining_tags)
        # toss an umlaut if applicable
        output = self.umlaut(output)
        # restore prefixes:
            # separable prefixes and inseparable in participles are joint at the beginning
            # else the prefix is separated 
        output = self.add_prefixes(prefixes, insep, output, 'Verbform=Part' not in target_tags)

        # use ADJInflector for participles,
        # as they inflect the same way
        if 'Verbform=Part' in target_tags:
            return self.adj_inflector(output, target_tags + '|Degree=Pos')
        
        return output
