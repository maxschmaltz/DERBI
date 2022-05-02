import setuptools

desc = '''
      DERBI (DEutscher RegelBasierter Inflektor) is a simple rule-based automatic 
      inflection model for German based on spaCy. Applicable regardless of POS!
       '''

setuptools.setup(
    name='DERBI',
    version=1.0,
    author='Max Schmaltz',
    authors_email='schmaltzmax@gmail.com',
    description=desc,
    packages=['DERBI']
)
