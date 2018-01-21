from setuptools import setup, find_packages

setup(
    name='configfile',
    version='1.2.2',
    description=('Dynamically parse and edit configuration files.'),
    long_description=('Dynamically parse and edit configuration files.'),
    url='https://github.com/kynikos/lib.py.configfile',
    author='Dario Giovannetti',
    author_email='dev@dariogiovannetti.net',
    license='GPLv3+',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Environment :: Console',
        'Intended Audience :: Developers',
        'Topic :: Software Development',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Text Processing',
        'License :: OSI Approved :: GNU General Public License v3 or later (GPLv3+)',  # noqa
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3.7',
    ],
    keywords='configuration parser development',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
)
