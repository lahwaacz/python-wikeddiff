#! /usr/bin/env python3

"""
Python-specific helpers for the WikEdDiff class.
"""

# Helper class to access dict elements both as attributes and items; with recursive constructor.
# source: https://stackoverflow.com/questions/3031219/python-recursively-access-dict-via-attributes-as-well-as-index-access/3031270#3031270
class dotdictify(dict):
    marker = object()
    def __init__(self, value=None):
        if value is None:
            pass
        elif isinstance(value, dict):
            for key in value:
                self.__setitem__(key, value[key])
        else:
            raise TypeError('expected dict')

    def __setitem__(self, key, value):
        if isinstance(value, dict) and not isinstance(value, dotdictify):
            value = dotdictify(value)
        super(dotdictify, self).__setitem__(key, value)

    def __getitem__(self, key):
        found = self.get(key, dotdictify.marker)
        if found is dotdictify.marker:
            found = dotdictify()
            super(dotdictify, self).__setitem__(key, found)
        return found

    __setattr__ = __setitem__
    __getattr__ = __getitem__


def int_or_null(value):
    if value is None:
        return 0
    return value
