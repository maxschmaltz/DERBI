import json
import re
import warnings

import spacy

import Tools, Inflectors

with open('Router.json') as r:
    Router = json.load(r)


class DeInflector:

    def __init__(self, model: spacy.lang.de.German):
        if not isinstance(model, spacy.lang.de.German):
            raise TypeError('You should use one of the German spaCy pipelines: https://spacy.io/models/de')
        self.model = model
        self.TagsProcessor = Tools.TagsProcessor()
        for pos, args in Router.items():
            inflector_name, fa_path, lexc_path = tuple(args)
            setattr(self, pos.lower() + '_inflector', getattr(Inflectors, inflector_name)(fa_path, lexc_path))

    def inflect(self, token: spacy.tokens.token.Token, target_tags: str):
        # check if the word consist of german abc letters
        german_abc_ext = re.compile('[^a-zäöüß]')
        if german_abc_ext.search(token.norm_) is not None:
            warnings.warn('Word "' + token.norm_ + '" contains invalid characters. It will not be processed.')
            return token.norm_

        if target_tags == '':
            warnings.warn('No tags for word "' + token.norm_ + '" were provided; it will not be inflected.', Warning)
            return token.norm_

        inflector = getattr(self, token.pos_.lower() + '_inflector')
        return inflector(token, target_tags)

    def __call__(self, text: str, target_tags: dict or list[dict]=None, indices: int or list[int]=None) -> str:

        if isinstance(target_tags, dict):
            if not len(target_tags):
                raise ValueError('At list one key-value pair required in target tags.')
            target_tags = [target_tags]
        if target_tags is None:
            warnings.warn('No tags were provided; none of the tokens will be inflected.', Warning)
            return text

        if isinstance(indices, int):
            indices = [indices]
        elif indices is None:
            indices = [0]

        if len(target_tags) != len(indices):
            raise ValueError('Number of indices and number of target tagsets must not differ.')

        self.doc = self.model(text)
        self.to_inflect = {
            str(ind): {
            'token': self.doc[ind],
            'target_tags': '' if not len(tagset) else self.TagsProcessor.sub_tags(self.doc[ind], tagset),
            } for ind, tagset in zip(indices, target_tags)}

        for data in self.to_inflect.values():
            data['result'] = self.inflect(data['token'], data['target_tags'])

        self.result_text = ' '.join([word.text if self.to_inflect.get(str(i)) is None else self.to_inflect[str(i)]['result'] 
                                                                                        for i, word in enumerate(self.doc)])
        return self.result_text
