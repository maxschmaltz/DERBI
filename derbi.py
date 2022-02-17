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

# import required modules
import json
import re
import warnings
# import spaCy
import spacy
# import required scripts
from DERBI import Tools, Inflectors
# Router contains information about 
# __init__ of each pos inflector
with open('DERBI/Router.json') as r:
    Router = json.load(r)

    
# wrapper for inflection
'''
In fact, we do not have an unified inflector,
we have an inflector for each POS.
To provide a comfortable usage experience, we must
organize a wrapper that would gather them all together 
to be able to call the needed one; so here it is! 
Wrapper performance consists of three stages:
    1. Take and process input.
        1.1. Create spacy Doc based on the input text;
        1.2. Make sure each to-be-inflected token has its own target tagset;
        1.3. Process the input features set: normalize, strip;
        merge and update (over the features of the given token);
        check if the tags are valid, make sure each tagset 
        is available for the POS of the given token;
    2. Redirect.
        2.1. For each to-be-inflected token define 
        which inflector it must be processed with;
        2.2. Call it and obtain the result;
    3. Assemble output.
        3.1. Replace all the to-be-inflected tokens 
        with the corresponding results in the input text.
        3.2. Return the result.
'''
class DERBI:

    def __init__(self, model: spacy.lang.de.German):
        # as the model uses spaCy, we require one of the German spaCy models;
        # any is accepted
        if not isinstance(model, spacy.lang.de.German):
            raise TypeError('You should use one of the German spaCy pipelines: https://spacy.io/models/de')
        self.model = model
        # with TagsProcessor we will process the input tags (surprisingly!) 
        self.TagsProcessor = Tools.TagsProcessor()
        # create an instance of inflector for each POS
        for pos, args in Router.items():
            inflector_name, fa_path, lexc_path = tuple(args)
            setattr(self, pos.lower() + '_inflector', getattr(Inflectors, inflector_name)(fa_path, lexc_path))

    def inflect(self, token: spacy.tokens.token.Token, target_tags: str) -> str:
        # check if the token consist of german abc letters
        german_abc_ext = re.compile('[^a-zäöüß]')
        if german_abc_ext.search(token.norm_) is not None:
            warnings.warn('Word "' + token.norm_ + '" contains invalid characters. It will not be processed.')
            return token.norm_
        # check if some tags were provided
        if target_tags == '':
            warnings.warn('No tags for word "' + token.norm_ + '" were provided; it will not be inflected.', Warning)
            return token.norm_
        # spaCy considers VERB Verbform=Part as ADJ, so we will catch it and redirect
        if (token.pos_ == 'ADJ') and (self.model(token.lemma_)[0].pos_ == 'VERB'):
            if re.search('nd(e[mnrs]{0,1}){0,1}$', token.text.lower()) is not None:
                return self.verb_inflector(self.model(token.lemma_), re.sub('Degree=\w+\|', '', target_tags) + 'Tense=Pres|Verbform=Part')
            else:
                return self.verb_inflector(self.model(token.lemma_), re.sub('Degree=\w+\|', '', target_tags) + 'Tense=Past|Verbform=Part')
        # define needed inflector and inflect
        inflector = getattr(self, token.pos_.lower() + '_inflector')
        return inflector(token, target_tags)

    def __call__(self, text: str, target_tags: dict or list[dict]=None, indices: int or list[int]=None) -> str:
        # check if the target tagsets and indices of to-be-inflected tokens were provided
        if isinstance(target_tags, dict):
#             if not len(target_tags):
#                 raise ValueError('At list one key-value pair required in target tags.')
            target_tags = [target_tags]
        if target_tags is None:
            warnings.warn('No tags were provided; none of the tokens will be inflected.', Warning)
            return text
        # if no indices were provided, set default as 0
        if isinstance(indices, int):
            indices = [indices]
        elif indices is None:
            indices = [0]
        # check the correspondance of the tagsets and the indices
        if len(target_tags) != len(indices):
            raise ValueError('Number of indices and number of target tagsets must not differ.')

        # process the input text with the given spaCy model
        self.doc = self.model(text)
        self.to_inflect = {
            str(ind): {
            'token': self.doc[ind],
            'target_tags': '' if not len(tagset) else self.TagsProcessor.sub_tags(self.doc[ind], tagset)
            } for ind, tagset in zip(indices, target_tags)}
        # obtain the results for each token
        for data in self.to_inflect.values():
            # check if anything changed
            if data['target_tags'] == str(data['token'].morph):
                data['result'] = data['token'].text.lower()
            else:
                data['result'] = self.inflect(data['token'], data['target_tags'])
        # assemble the result
        self.result_text = ' '.join([word.text if self.to_inflect.get(str(i)) is None else self.to_inflect[str(i)]['result'] 
                                                                                for i, word in enumerate(self.doc)]).lower()
        return self.result_text
