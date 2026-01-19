#!/usr/bin/env python
import sys

from setuptools import find_packages, setup

long_description = ""

if "sdist" in sys.argv:
    with open("README.rst") as f:
        long_description = f.read()


setup(
    name="slider",
    version="0.8.4",
    description="Utilities for working with osu! files and data",
    author="Joe Jevnik",
    author_email="joejev@gmail.com",
    packages=find_packages(),
    long_description=long_description,
    license="LGPLv3+",
    classifiers=[
        "Development Status :: 3 - Alpha",
        "License :: OSI Approved :: GNU Lesser General Public License v3 or later (LGPLv3+)",  # noqa
        "Natural Language :: English",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3 :: Only",
        "Topic :: Games/Entertainment",
    ],
    url="https://github.com/llllllllll/slider",
    install_requires=[
        "numpy",
        "requests",
        "scipy",
    ],
    extras_require={
        "dev": [
            "ruff",
            "shed",
            "pytest",
        ],
        "cli": [
            "click",
        ],
    },
)
