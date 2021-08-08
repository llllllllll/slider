#!/usr/bin/env python
from setuptools import setup, find_packages
import sys

long_description = ''

if 'sdist' in sys.argv:
    with open('README.rst') as f:
        long_description = f.read()


setup(
    name='slider',
    version='0.5.2',
    description='Utilities for working with osu! files and data',
    author='Joe Jevnik',
    author_email='joejev@gmail.com',
    packages=find_packages(),
    long_description=long_description,
    license='LGPLv3+',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)',  # noqa
        'Natural Language :: English',
        'Programming Language :: Python :: 3.6',
        'Programming Language :: Python :: 3 :: Only',
        'Topic :: Games/Entertainment',
    ],
    url='https://github.com/llllllllll/slider',
    install_requires=[
        'click',
        'numpy',
        'requests',
        'scipy',
    ],
    extras_require={
        'dev': [
            'flake8==3.7.9',
            'mccabe==0.6.1',
            'pyflakes==2.1.1',
            'pytest==5.4.1',
        ],
    },
)
