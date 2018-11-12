from setuptools import setup, find_packages

setup(
    name='configfile',
    version='1.2.4',
    description='Dynamically parse and edit configuration files.',
    long_description='Dynamically parse and edit configuration files with '
        'support for subsections.',
    url='https://github.com/kynikos/lib.py.configfile',
    author='Dario Giovannetti',
    author_email='dev@dariogiovannetti.net',
    license='MIT',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing',
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='configuration parser development',
    packages=find_packages(exclude=['contrib', 'dev', 'docs', 'tests']),
)
