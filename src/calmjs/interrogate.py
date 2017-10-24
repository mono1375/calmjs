# -*- coding: utf-8 -*-
"""
For the purpose of interrogation of JavaScript source files.
"""

from __future__ import absolute_import

import logging
import re
from functools import partial

from calmjs.parse import asttypes
from calmjs.parse.parsers.es5 import parse

logger = logging.getLogger(__name__)
strip_quotes = partial(re.compile('([\"\'])(.*)(\\1)').sub, '\\2')
strip_slashes = partial(re.compile(r'\\(.)').sub, '\\1')

define_wrapped = dict(enumerate(('require', 'exports', 'module',)))
reserved_module = {'module'}


def to_str(ast_string):
    return strip_slashes(strip_quotes(ast_string.value))


def to_identifier(node):
    # if the node is a string, assume it is used as a BracketAccessor
    if isinstance(node, asttypes.String):
        # We are leveraging the similarity of string encoding between
        # ES5 and Python, but to achieve this is a bit of work.
        # First, the quotes must be stripped ([1:-1]), then use the
        # unicode-escape to encode all the things - and then strip off
        # the doubly escaped backslashes for everything and bring it
        # back by decoding again with unicode-escape.
        return node.value[1:-1].encode('unicode-escape').replace(
            b'\\\\', b'\\').decode('unicode-escape')
    else:
        # assume to be an Identifier
        return node.value


def shallow_filter(program, condition):
    for child in program:
        if condition(child):
            yield child
        else:
            for subchild in shallow_filter(child, condition):
                yield subchild


def deep_filter(program, condition):
    for child in program:
        if condition(child):
            yield child
        for subchild in deep_filter(child, condition):
            yield subchild


def yield_function(program, filter_func=shallow_filter):
    for node in filter_func(program, lambda node: (
            isinstance(node, asttypes.FunctionCall) and
            isinstance(node.identifier, asttypes.Identifier))):
        yield node


def filter_function_argument(program, f_name, f_argn, f_argt):
    for node in yield_function(program):
        if (node.identifier.value == f_name and f_argn < len(node.args.items)
                and isinstance(node.args.items[f_argn], f_argt)):
            yield to_str(node.args.items[f_argn])


def extract_function_argument(text, f_name, f_argn, f_argt=asttypes.String):
    """
    Extract a specific argument from a specific function name.

    Arguments:

    text
        The source text.
    f_name
        The name of the function
    f_argn
        The argument position
    f_argt
        The argument type from calmjs.parse.asttypes;
        default: calmjs.parse.asttypes.String
    """

    tree = parse(text)
    return list(filter_function_argument(tree, f_name, f_argn, f_argt))


def yield_require_list_arguments(
        node, pos,
        reserved_module=reserved_module, wrapped=define_wrapped):
    """
    This is for generating the list of imports for the given node, which
    must be of the FunctionCall type.
    """

    for i, child in enumerate(node.args.items[pos]):
        if isinstance(child, asttypes.String):
            result = to_str(child)
            if ((result not in reserved_module) and (
                    result != define_wrapped.get(i))):
                yield result
        # otherwise it is a variable of some kind and dynamic imports
        # will have to be derived by some other means.


def yield_require_argument(node, pos):
    yield to_str(node.args.items[pos])


import_checks = (
    (partial(yield_require_argument, pos=0), lambda node: (
        len(node.args.items) == 1 and
        isinstance(node.args.items[0], asttypes.String) and
        node.identifier.value == 'require'
    )),
    (partial(yield_require_list_arguments, pos=0), lambda node: (
        len(node.args.items) >= 2 and
        isinstance(node.args.items[0], asttypes.Array) and
        isinstance(node.args.items[1], asttypes.FuncExpr) and
        node.identifier.value == 'require'
    )),
    (partial(yield_require_list_arguments, pos=0), lambda node: (
        len(node.args.items) >= 2 and
        isinstance(node.args.items[0], asttypes.Array) and
        isinstance(node.args.items[1], asttypes.FuncExpr) and
        node.identifier.value == 'define'
    )),
    (partial(yield_require_list_arguments, pos=1), lambda node: (
        len(node.args.items) >= 3 and
        isinstance(node.args.items[0], asttypes.String) and
        isinstance(node.args.items[1], asttypes.Array) and
        isinstance(node.args.items[2], asttypes.FuncExpr) and
        node.identifier.value == 'define'
    )),
)


def yield_module_imports(root, checks=import_checks):
    """
    Gather all require and define calls from unbundled JavaScript source
    files and yield all module names.  The imports can either be of the
    CommonJS or AMD syntax.
    """

    for child in yield_function(root, deep_filter):
        for f, condition in checks:
            if condition(child):
                for name in f(child):
                    yield name
                continue


def extract_module_imports(text):
    """
    Extract all require and define calls from unbundled JavaScript
    source files in both AMD and CommonJS syntax.
    """

    tree = parse(text)
    return yield_module_imports(tree)