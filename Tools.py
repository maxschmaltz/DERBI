# Copyright 2022 Max Schmaltz: @maxschmaltz
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ************************************************************************

# import required modules / functions
from numpy import argmin
from collections import defaultdict
import json
import re
import warnings
# import spaCy
import spacy

# obtain required json data
with open('DERBI/meta/LabelsScheme.json') as json_file:
    LabelsScheme = json.load(json_file)
    
with open('DERBI/meta/ValidFeatures.json') as json_file:
    ValidFeatures = json.load(json_file)

# json data links
labels_scheme_link = 'https://github.com/maxschmaltz/DERBI/blob/main/meta/LabelsScheme.json'
valid_features_link = 'https://github.com/maxschmaltz/DERBI/blob/main/meta/ValidFeatures.json'

# transform Universal Features 'Name=Value' notation to python dict, for example, 
# 'Case=Nom|Gender=Masc|Number=Plur' -> {'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur'} 
def split_tags(tags: str) -> dict:
    if tags == '':
        return {}
    return {cat_feat.split('=')[0]: cat_feat.split('=')[1] for cat_feat in tags.split('|')}

# do the opposite, for example,
# {'Case': 'Nom', 'Gender': 'Masc', 'Number': 'Plur'} -> 'Case=Nom|Gender=Masc|Number=Plur' 
def merge_tags(tags: dict) -> str:
    return '|'.join([cat + '=' + feat for cat, feat in tags.items()])


# TagsSearcher takes a tagset and compares it to data presented in out json data:
# searches if the tagset is in LabelsScheme; sets default values in accordance with ValidFeatures
class TagsSearcher:

    # refer to ValidFeatures to check the input categories and features are valid 
    def check_tags(self, tags: dict):
        for cat, feat in tags.items():
            # check the category (for example, 'PP', 'VVN' are not accepted)
            if ValidFeatures.get(cat) is None:
                raise ValueError('Category "' + cat + '" is not supported.\nValid categories are available at ' 
                                 + valid_features_link + '.')
            # check the feature (for example, 'Dat' is not accepted for 'Number')
            if feat not in ValidFeatures[cat]:
                raise ValueError('Feature "' + feat + '" is not valid for category "' + cat + 
                                 '".\nValid features are available at ' + valid_features_link + '.')
    
    # primary search checks strict match
    def primary_search(self, morph: str, pos: str) -> bool:
        self.check_tags(split_tags(morph))
        return morph not in LabelsScheme.get(pos, [])

    # secondary search checks partial match: if in label scheme there is such a tagset
    # that for each category-feature pair in it either the feature is in target tagset or 
    # the category is missing there
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

        # then if we found such a tagset, we want to set our 
        # target tagset's missing categories as default;
        # the default value for each category is [0] element of its list in ValidFeatures 
        extract_min = lambda m: m[argmin([len(f.split('|')) for f in m])]
        res_tags = merge_tags({cat: (ValidFeatures[cat][0] if morph_tags.get(cat) is None 
                                     else morph_tags[cat]) for cat, feat in split_tags(extract_min(matches)).items()})
        warnings.warn('Provided tags were not found in labels scheme. Some features were set as default.\nResult features are "' +
                      res_tags + '". You can specify desired features if you wish.\nLabels scheme is available at: ' + labels_scheme_link + '.', Warning)
        return res_tags

    
# TagsProcessor contains methods for input tags transformation
# the way we need it
class TagsProcessor:

    def __init__(self):
        self.Searcher = TagsSearcher()

    # we want all the tags to be normalized for us not to depend on the case
    def normalize_tags(self, tags: dict) -> dict:
        return {key.capitalize().strip(): value.capitalize().strip() for key, value in tags.items()}

    # not all the categories can be alternated
    def filter_target_tags(self, tagset: dict, tok: spacy.tokens.token.Token):
        pos = tok.pos_
        self.filter = {
            'ADV': ['PronType'],
            'DET': ['Definite', 'Prontype', 'Poss'],
            'NOUN': ['Gender'],
            'PRON': ['PronType', 'Poss'],
            'PROPN': ['Gender'],
            'SCONJ': ['Prontype'],
            'X': ['Foreign']
        }
        # let NOUNs with adjective declination pass           
        if (pos == 'NOUN') and (tagset.get('Declination') is not None):
            return
        # apply filter
        curr_filter = self.filter.get(pos, [])
        for key in tagset.keys():
            if key == 'Prontype':
                actual_feat = tok.morph.get('PronType')
            else:
                actual_feat = tok.morph.get(key)
            if ((key in curr_filter) and (not len(actual_feat)) or
                (key in curr_filter) and (tagset[key] != actual_feat[0])):
                raise ValueError('Category "' + key + '" cannot be alternated for POS "' + pos + '".')


    # main tags processing function 
    def sub_tags(self, tok: spacy.tokens.token.Token, target_tags: dict) -> str:
        target_tags = self.normalize_tags(target_tags)
        lemma, morph, pos = tok.lemma_, tok.morph, tok.pos_
        self.filter_target_tags(target_tags, tok)

        morph_tags = self.normalize_tags(split_tags(str(morph)))
        # merge and update the features
        target_morph = '|'.join([cat + '=' + (feat if target_tags.get(cat) is None else target_tags[cat]) 
                        for cat, feat in sorted({**morph_tags, **target_tags}.items())])
        
        # replace some features for AUXs and VERBs
        if (tok.pos_ in ['AUX', 'VERB']) and ('Verbform=Part' in target_morph):
            target_morph = re.sub('Mood=\w+\|', '', target_morph)
            target_morph = re.sub('Person=\w+\|', '', target_morph)     
            
        if ('Verbform=' not in target_morph) and (morph.get('VerbForm') == 'Inf'):
            target_morph = re.sub('VerbForm=Inf', '', target_morph)

        # check if the features are supported
        search_failed = self.Searcher.primary_search(target_morph, pos)
        if not search_failed:
            return target_morph

        if pos in ['ADJ', 'ADP', 'AUX', 'DET', 'NOUN', 'PRON', 'PROPN', 'VERB']:
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
        
        
''' 
The following classes are essential for DERBI.
We have two ways to inflect words:
    1. Lexicons. 
        Lexicons are applicable when we need to process a special case,
        that does not correspond to the regular inflection model, i.e. exception;
        As sometimes only stem, not the whole word, inflects different, 
        we would like to leave an opportunity to apply rules with 
        partial match of the features; for that we check partial match 
        and remove all the features that have been matched (for them
        not to be used in automata, see below).
        For example, for Tense=Past of VERBs we often inflect only stems
        with lexicon, and the flexion is added in automata
        in accordance to the regular model (bringen+Tense=Past|Person,Number...) ->
        -> brachte+Person,Number... -> ...
    2. Automata.
        Automata describe regular models. Unlike lexicon, regular model
        requires full match.
Despite the difference between the two ways, the general approach is the same:
for each rule we check if it's applicable and, if it is, we replace the part of the word
the way defined in the rule.
'''
'''
Each rule consists of three parts:
    1. Re pattern to be substituted;
    2. Conditions of applicability;
    3. Substring the match must be substituted with.
    
Rules are written as:
1+2->3

Conditions of applicability are usual 'Name=Value' notation 
with some extentions:
    1. Multiple choice is possible (Case=[C1,C2,C3] is for Case=C1 or Case=C2 or ...);
    2. Independance is possible (Case=* if for any valid Case);
    3. Exclusion is possible (Case=[^C1] if for any valid Case but C1).
'''
class Lexicon:

    def __init__(self, rules_path: str):
        with open(rules_path, 'r') as rules_file:
            rules = [line for line in rules_file]
        self.rules = defaultdict(list)
        # notation extentions patterns
        self.exclude_pattern = re.compile('(?<=\[\^)(\w+,{0,1})+(?=\])')
        self.multiple_pattern = re.compile('(?<=\[)(\w+,{0,1})+(?=\])')
        # collect the rules from text file
        for rule in rules:
            self.interpret(rule)

    def interpret(self, rule: str):
        try: 
            splitted = re.split('\+|->', rule)
            # 1, 2, 3 (see above)
            input, feats, output = splitted[0], splitted[1], splitted[2]
            splitted_feats = split_tags(feats)
            rule_dict = {}
            # interpret considering extentions
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

    def __init__(self, rules_path: str):
        with open(rules_path, 'r') as rules_file:
            rules = [line for line in rules_file]
        self.rules = []
        # notation extentions patterns
        self.exclude_pattern = re.compile('(?<=\[\^)(\w+,{0,1})+(?=\])')
        self.multiple_pattern = re.compile('(?<=\[)(\w+,{0,1})+(?=\])')
        # collect the rules from text file
        for rule in rules:
            self.interpret(rule)

    def interpret(self, rule: str):
        try: 
            splitted = re.split('\+|->', rule)
            # 1, 2, 3 (see above)
            pattern, feats, to_sub = splitted[0], splitted[1], splitted[2]
            splitted_feats = split_tags(feats)
            rule_dict = {}
            # interpret considering extentions
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
