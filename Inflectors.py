# import spacy
# import Tools
import re

# Basic Parent Class
class BasicInflector:

    def __init__(self, fa_path=None, lexc_path=None):
        self.auto_rules, self.lexc_rules = None, None

        if fa_path is not None:
            self.auto_rules = Tools.StateMachine(fa_path).rules
        if lexc_path is not None:
            self.lexc_rules = Tools.Lexicon(lexc_path).rules

    def search_in_lexicon(self, lemma, target_tags: str):
        if (self.lexc_rules is None) or (self.lexc_rules.get(lemma) is None):
            return lemma, Tools.split_tags(target_tags)
        else:
            tags_dict = Tools.split_tags(target_tags)
            curr_rules = self.lexc_rules[lemma]
            for rule in curr_rules:
                rule_is_applicable = set([((rule['rule'].get(cat) is None) or (feat in rule['rule'][cat])) 
                                      for cat, feat in tags_dict.items()]) == {True}
                if rule_is_applicable:
                    return rule['output'], {cat: feat for cat, feat in tags_dict.items() if rule['rule'].get(cat) is None}
            else:
                return lemma, Tools.split_tags(target_tags)

    def automata(self, token: str, tags_dict: dict):
        if self.auto_rules is None:
            return token

        for rule in self.auto_rules:
            rule_is_applicable = (set([tags_dict.get(cat, '') in rule['rule'][cat]  
                                  for cat, feat in rule['rule'].items()]) == {True}) or (rule['rule'] == {})
            if rule_is_applicable:
                token = re.sub(rule['pattern'], rule['to_sub'], token)
            # print(rule, token)
        return token

    def __call__(self, token, target_tags):
        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output

        return self.automata(output, remaining_tags)


# CCONJ, INTJ, NUM, PART, SCONJ, X
class Uninflected(BasicInflector):

    def search_in_lexicon(self, *args):
        pass

    def automata(self, *args):
        pass

    def __call__(self, token, _):
        return token.norm_


# ADJ, ADV
class ADJInflector(BasicInflector):
    
    def umlaut(self, token: str):
        if token.count('#') != 1:
            return token.replace('#', '')
        token = re.sub('#a', 'ä', token)
        token = re.sub('#o', 'ö', token)
        token = re.sub('#u', 'ü', token)
        # if not applicable, there is no umlaut
        return token.replace('#', '')

    def __call__(self, token, target_tags):
        # from AUX and VERB we can receive <str> tokens,
        # so we must just pass the following part then
        if not isinstance(token, str):
            # somehow for ADV spacy add 'en' to lemma in Degree=Pos,
            # e.g. 'schnell'.lemma_ = 'schnellen' but 'schneller'.lemma_ = 'schnell'
            if (token.pos_ == 'ADV') and (token.text + 'en' == token.lemma_.lower()):
                token.lemma_ = token.text

            # somehow for ADV spacy add 'e' to lemma in some forms,
            # e.g. 'rote'.lemma_ = 'rote' but 'roten'.lemma_ = 'rot'
            if (token.pos_ == 'ADJ') and (token.lemma_.lower()[-1] == 'e'):
                token.lemma_ = token.lemma_.lower()[:-1]

            output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
            if not(len(remaining_tags)):
                return output
        else:
            output = token
            remaining_tags = Tools.split_tags(target_tags)
            
        auto_output = self.automata(output, remaining_tags)
        return self.umlaut(auto_output)


# ADP
class ADPInflector(BasicInflector):

    def automata(self, token: str, target_tags):
        # if an adposition came through the lexc and returned with
        # remaining tags, it means it's not there (as APD.lexc defines 
        # all the features); then we're trying to inflect the adp to 
        # a form it can't have
        if len(target_tags):
            raise ValueError('Features "' + target_tags + 
                            '" are not available for word "' + token.norm_ + '".')
        return token.norm_


# AUX
class AUXInflector(BasicInflector):

    def __init__(self, fa_path=None, lexc_path=None):
        super().__init__(fa_path, lexc_path)
        self.adj_inflector = ADJInflector('meta/automata/ADJ.fa')

    def umlaut(self, token: str):
        if '&' not in token:
            return token

        past_stem = token[:token.index('&')]
        sub_stem = re.sub('a', 'ä', past_stem)
        sub_stem = re.sub('o', 'ö', sub_stem)
        sub_stem = re.sub('u', 'ü', sub_stem)
        return re.sub('^' + past_stem + '&', sub_stem, token)

    def __call__(self, token, target_tags):
        if ((token.lemma_.lower() in ['dürfen', 'können', 'mögen', 'müssen', 'sollen', 'wollen'])
                                                                and ('Mood=Imp' in target_tags)):
            raise ValueError('No Imperative forms available for modal verbs.')

        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output

        output = self.automata(output, remaining_tags)
        output = self.umlaut(output)

        if 'Verbform=Part' in target_tags:
            return self.adj_inflector(output, target_tags + '|Degree=Pos')
        
        return output


# DET
class DETInflector(BasicInflector):

    def parse_poss_dets(self, token):
        # euer is distinct, as it has a prothetical vowel
        euer_pattern = re.compile('eue{0,1}r')
        # no 'mein', because 'mein' is default
        poss_pattern = re.compile('([ds]ein)|unser|ihr')

        if euer_pattern.search(token.text) is not None:
            token.lemma_ = 'euer'

        elif poss_pattern.search(token.text) is not None:
            token.lemma_ = poss_pattern.search(token.text)[0]

    def __call__(self, token, target_tags):
        if ((token.lemma_.lower() == 'ein') or (token.lemma_.lower() == 'einen')) and ('Number=Plur' in target_tags):
            raise ValueError('Article "ein" has only Singular forms.')

        if (token.lemma_.lower() in ['mein', 'meinen', 'sich']) and ('Poss=Yes' in str(token.morph)):
            self.parse_poss_dets(token)

        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output

        return self.automata(output, remaining_tags)


# NOUN
class NOUNInflector(BasicInflector):

    def __init__(self, fa_path=None, lexc_path=None):
        super().__init__(fa_path, lexc_path)
        self.adj_inflector = ADJInflector('meta/automata/ADJ.fa')

    def __call__(self, token, target_tags):
        
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
        output, remaining_tags = self.search_in_lexicon(splitted[1].lower(), target_tags)
        if not(len(remaining_tags)):
            return output
        
        return splitted[0].lower() + self.automata(output, remaining_tags)


# PRON
class PRONInflector(BasicInflector):

    def __call__(self, token, target_tags):
        
        if 'Reflex=Yes' in target_tags:
            target_tags = target_tags.replace('PronType=Prs|', '')

        if 'Prontype=Prs' in target_tags:
            token.lemma_ = 'ich'

        output, remaining_tags = self.search_in_lexicon(token.lemma_.lower(), target_tags)
        if not(len(remaining_tags)):
            return output
        
        return self.automata(output, remaining_tags)


# PROPN
class PROPNInflector(BasicInflector):

    def search_in_lexicon(self, lemma, target_tags: str):
        pass

    def __call__(self, token, target_tags):
        tags_dict = Tools.split_tags(target_tags)
        return self.automata(token.lemma_.lower(), tags_dict)


# VERB
class VERBInflector(AUXInflector):

    def __init__(self, fa_path=None, lexc_path=None):
        super().__init__(fa_path, lexc_path)
        with open('meta/lexicons/verb_prefixes.json') as j:
            self.prefixes = json.load(j)

    def sep_prefixes(self, token: str):
        stem = re.sub('(en$|(?<=[lr])n$|(?<=tu)n$|(?<=sei)n$)', '', token)
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
        prefixes_pattern = re.compile('^' + '|^'.join(self.prefixes['sep'] + self.prefixes['insep']))
        while prefixes_pattern.search(stem) is not None:
            pref = prefixes_pattern.search(stem)[0]
            if syls(re.sub(pref, '', stem)) == 0:
                break
            prefs.append(pref)
            stem = re.sub(pref, '', stem, count=1)

        if not len(prefs):
            return ('', False, token)
        
        restore_dis = lambda x, matches: x if not len(matches) else restore_dis(re.sub(matches[-1], 
                                    {v: k for k, v in dis.items()}[matches[-1]], x), matches[:-1])

        insep = ((prefs[0] in self.prefixes['insep']) or (prefs[-1] in self.prefixes['insep']))
        prefs = restore_dis(''.join(prefs), re.findall('|'.join({v: k for k, v in dis.items()}.keys()), ''.join(prefs)))
        return prefs, insep, re.sub('^' + prefs, '', token)

    def add_prefixes(self, prefixes, insep, token, separate):
        if not len(prefixes):
            return re.sub('#', 'ge', token)
        
        if insep:
            return prefixes + re.sub('#', '', token)

        if separate:
            return '(' + token + ' , ' + prefixes + ') '
        
        return prefixes + re.sub('#', 'ge', token)

    def __call__(self, token, target_tags):
        if ((token.lemma_.lower() in ['dürfen', 'können', 'mögen', 'müssen', 'sollen', 'wollen'])
                                                                and ('Mood=Imp' in target_tags)):
            raise ValueError('No Imperative forms available for modal verbs.')

        prefixes, insep, stem = self.sep_prefixes(token.lemma_.lower())

        output, remaining_tags = self.search_in_lexicon(stem, target_tags)
        if not(len(remaining_tags)):
            return output

        output = self.automata(output, remaining_tags)
        output = self.umlaut(output)
        output = self.add_prefixes(prefixes, insep, output, 'Verbform=Part' not in target_tags)

        if 'Verbform=Part' in target_tags:
            return self.adj_inflector(output, target_tags + '|Degree=Pos')
        
        return output
