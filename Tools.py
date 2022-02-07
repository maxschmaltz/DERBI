import json
import re
from collections import defaultdict
import warnings
from numpy import argmin
import spacy


with open('meta/LabelsScheme.json') as json_file:
    LabelsScheme = json.load(json_file)

with open('meta/DefaultTags.json') as json_file:
    DefaultTags = json.load(json_file)
    
with open('meta/ValidFeatures.json') as json_file:
    ValidFeatures = json.load(json_file)


labels_scheme_link = 'https://github.com/maxschmaltz/DeInflector/blob/main/meta/LabelsScheme.json'
valid_features_link = 'https://github.com/maxschmaltz/DeInflector/blob/main/meta/ValidFeatures.json'

def split_tags(tags: str) -> dict:
    if tags == '':
        return {}
    return {cat_feat.split('=')[0]: cat_feat.split('=')[1] for cat_feat in tags.split('|')}

def merge_tags(tags: dict) -> str:
    return '|'.join([cat + '=' + feat for cat, feat in tags.items()])


class TagsSearcher:

    def check_tags(self, tags: dict):
        for cat, feat in tags.items():
            if ValidFeatures.get(cat) is None:
                raise ValueError('Category "' + cat + '" is not supported.\nValid categories are available at ' 
                                 + valid_features_link + '.')
            if feat not in ValidFeatures[cat]:
                raise ValueError('Feature "' + feat + '" is not valid for category "' + cat + 
                                 '".\nValid features are available at ' + valid_features_link + '.')
    
    def primary_search(self, morph: str, pos: str) -> bool:
        self.check_tags(split_tags(morph))
        return morph not in LabelsScheme.get(pos, [])

    def secondary_search(self, morph: str, pos: str) -> None or str:
        morph_tags = split_tags(morph)
        self.check_tags(morph_tags)
        pattern = re.compile('(\\||^)' + '\\|(\\w+=\\w+\\|)*'.join([cat + '=' + feat 
                            for cat, feat in sorted(morph_tags.items())]) + '(\\||$)')
        matches = []
        for feats in LabelsScheme.get(pos, []):
            if pattern.search(feats) is not None:
                matches.append(feats)
        if not len(matches):
            return

        extract_min = lambda m: m[argmin([len(f.split('|')) for f in m])]
        res_tags = merge_tags({cat: (DefaultTags[cat] if morph_tags.get(cat) is None 
                                     else morph_tags[cat]) for cat, feat in split_tags(extract_min(matches)).items()})
        warnings.warn('Provided tags were not found in labels scheme. Some features were set as default.\nResult features are "' +
                      res_tags + '". You can specify desired features if you wish.\nLabels scheme is available at: ' + labels_scheme_link + '.', Warning)
        return res_tags

    
class TagsProcessor:

    def __init__(self):
        self.Searcher = TagsSearcher()

    def normalize_tags(self, tags: dict) -> dict:
        return {key.capitalize().strip(): value.capitalize().strip() for key, value in tags.items()}

    def filter_target_tags(self, tagset: dict, pos: str):
        self.filter = {
            'ADV': ['PronType'],
            'DET': ['Definite', 'Prontype', 'Poss'],
            'NOUN': ['Gender'],
            'PRON': ['PronType', 'Poss'],
            'PROPN': ['Gender'],
            'SCONJ': ['Prontype'],
            'X': ['Foreign']
        }
        curr_filter = self.filter.get(pos, [])
        for key in tagset.keys():
            if key in curr_filter:
                raise ValueError('Category "' + key + '" cannot be alternated for POS "' + pos + '".')

    def sub_tags(self, tok: spacy.tokens.token.Token, target_tags: dict) -> str:
        target_tags = self.normalize_tags(target_tags)
        lemma, morph, pos = tok.lemma_, tok.morph, tok.pos_
        self.filter_target_tags(target_tags, pos)

        morph_tags = self.normalize_tags(split_tags(str(morph)))
        # merge and update the features
        target_morph = '|'.join([cat + '=' + (feat if target_tags.get(cat) is None else target_tags[cat]) 
                        for cat, feat in sorted({**morph_tags, **target_tags}.items())])
        
        # check if anything changed
        if target_morph == str(morph):
            return str(morph)

        # check if the features are supported
        search_failed = self.Searcher.primary_search(target_morph, pos)
        if not search_failed:
            return target_morph

        if pos in ['ADJ', 'ADP', 'AUX', 'NOUN', 'PROPN', 'VERB']:
            # additional stage for the POSs that can have any forms:
            # there's a chance that the user did not insert all the tags
            # so we will fill it out as default if necessary
            res_tags = self.Searcher.secondary_search(target_morph, pos)
            if res_tags is None:
                raise ValueError('Features "' + target_morph + '" are not supported for POS "' + pos + 
                                 '".\nLabels scheme is available at: ' + labels_scheme_link + '.')
            return res_tags

        # if the POS cannot have any forms and the features are not supported:
        # we cannot inflect that
        raise ValueError('Features "' + target_morph + '" are not supported for word "' + lemma + 
                         '" of POS "' + pos + '".\nLabels scheme is available at: ' + labels_scheme_link + '.')
        
        
class Lexicon:

    def __init__(self, rules_path):
        with open(rules_path, 'r') as rules_file:
            rules = [line for line in rules_file]
        self.rules = defaultdict(list)
        self.exclude_pattern = re.compile('(?<=\[\^)(\w+,{0,1})+(?=\])')
        self.multiple_pattern = re.compile('(?<=\[)(\w+,{0,1})+(?=\])')
        for rule in rules:
            self.interpret(rule)

    def interpret(self, rule):
        try: 
            splitted = re.split('\+|->', rule)
            input, feats, output = splitted[0], splitted[1], splitted[2]
            splitted_feats = split_tags(feats)
            rule_dict = {}
            for cat, feat in splitted_feats.items():
                if feat == '*':
                    rule_dict[cat] = ValidFeatures[cat]
                elif self.exclude_pattern.search(feat) is not None:
                    to_exclude = self.exclude_pattern.search(feat)[0].split(',')
                    rule_dict[cat] = [c for c in ValidFeatures[cat] if c not in to_exclude]
                elif self.multiple_pattern.search(feat) is not None:
                    multiple_choice = self.multiple_pattern.search(feat)[0].split(',')
                    rule_dict[cat] = multiple_choice
                else:
                    rule_dict[cat] = [feat]
            self.rules[input].append({'rule': rule_dict, 'output': output.strip()})
        except: pass


class StateMachine:

    def __init__(self, rules_path):
        with open(rules_path, 'r') as rules_file:
            rules = [line for line in rules_file]
        self.rules = []
        self.exclude_pattern = re.compile('(?<=\[\^)(\w+,{0,1})+(?=\])')
        self.multiple_pattern = re.compile('(?<=\[)(\w+,{0,1})+(?=\])')
        for rule in rules:
            self.interpret(rule)

    def interpret(self, rule):
        try: 
            splitted = re.split('\+|->', rule)
            pattern, feats, to_sub = splitted[0], splitted[1], splitted[2]
            splitted_feats = split_tags(feats)
            rule_dict = {}
            for cat, feat in splitted_feats.items():
                if feat == '*':
                    rule_dict[cat] = ValidFeatures[cat]
                elif self.exclude_pattern.search(feat) is not None:
                    to_exclude = self.exclude_pattern.search(feat)[0].split(',')
                    rule_dict[cat] = [c for c in ValidFeatures[cat] if c not in to_exclude]
                elif self.multiple_pattern.search(feat) is not None:
                    multiple_choice = self.multiple_pattern.search(feat)[0].split(',')
                    rule_dict[cat] = multiple_choice
                else:
                    rule_dict[cat] = [feat]
            self.rules.append({'pattern': pattern, 'rule': rule_dict, 'to_sub': to_sub.replace('\n', '')})
        except: pass  
