#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
from setuptools import setup
import re
import sys

PACKAGE_NAME = "gptf"

string_literal = r"""['"]((\"|\'|[^'"])*)['"]"""
literal_line = r"^__(\w*)__\s*=\s*{}".format(string_literal)
args_needed = ['version', 'author']
kw_args = {}

# load package info from __init__.py
infofile = "{}/__init__.py".format(PACKAGE_NAME)
with open(infofile) as f:
    for line in f:
        match = re.search(literal_line, line, re.M)
        if match:
            key = match.group(1)
            value = match.group(2)
            if key == 'author':
                submatch = re.search('^([\w ]*) <([^>]*)>', value)
                if submatch:
                    value = submatch.group(1)
                    kw_args['author_email'] = submatch.group(2)
            if key in args_needed:
                kw_args[key] = value

if not all(kw_args.get(arg, None) for arg in args_needed):
    raise RuntimeError("Unable to find required info in {}".format(infofile))

kw_args['install_requires'] =\
        [ 'scipy'
        , 'numpy'
        , 'future>=0.15'
        , 'overrides>=1.7'
        ]

# tensorflow is also available under the name tensorflow-gpu. Don't install
# the cpu version if the gpu version is available.
try:
    import tensorflow as tf
    assert tf.__version__ >= '1.0'
except (ImportError, AssertionError):
    kw_args['install_requires'].append(['tensorflow>=1.0'])

kw_args['dependency_links'] = []
kw_args['tests_require'] = []
if sys.version[:1] == '2':
    kw_args['install_requires'].extend(['contextlib2>=0.5', 'funcsigs'])

setup\
        ( name=PACKAGE_NAME
        , url='https://github.com/ICL-SML/gptf'
        , description=
            ( "Distributed GPs using TensorFlow." )
        , packages=
            [ PACKAGE_NAME, PACKAGE_NAME + '.core' ]
        , setup_requires=
            [ 'nose>=1.0' ]
        , classifiers=
            [ "Natural Language :: English"
            , "Programming Language :: Python :: 2.7"
            , "Programming Language :: Python :: 3.4"
            , "Programming Language :: Python :: 3.5"
            , "Programming Language :: Python :: 3.6"
            , "Topic :: Scientific/Engineering :: Artificial Intelligence"
            ]
        , **kw_args
        )

