#! /usr/bin/env python3

"""
Main data structures used in the WikEdDiff class. In the original JavaScript
code they were represented as plain tables, but in Python we need to create
custom objects.

See diff.py for documentation.
"""

from __future__ import annotations
from dataclasses import dataclass


##
## Token element.
##
## @class Token
##
@dataclass
class Token:
    token: str
    prev: Token
    next: Token
    link: int
    number: int
    unique: bool

##
## Symbols table.
##
## @class Symbols
##
@dataclass
class Symbols:
    token: list
    hashTable: dict
    linked: bool

##
## Symbol element.
##
## @class Symbol
##
@dataclass
class Symbol:
    newCount: int
    oldCount: int
    newToken: int
    oldToken: Token


##
## Gap element.
##
## @class Gap
##
@dataclass
class Gap:
    newFirst: int
    newLast: int
    newTokens: int
    oldFirst: int
    oldLast: int
    oldTokens: int
    charSplit: bool

##
## Block element.
##
## @class Block
##
@dataclass
class Block:
    oldBlock: int
    newBlock: int
    oldNumber: int
    newNumber: int
    oldStart: int
    count: int
    unique: bool
    words: int
    chars: int
    type: str
    section: int
    group: int
    fixed: bool
    moved: bool
    text: str

##
## Section element.
##
## @class Section
##
@dataclass
class Section:
    blockStart: int
    blockEnd: int


##
## Group element.
##
## @class Group
##
@dataclass
class Group:
    oldNumber: int
    blockStart: int
    blockEnd: int
    unique: bool
    maxWords: int
    words: int
    chars: int
    fixed: bool
    movedFrom: int
    color: int


##
## Fragment element.
##
## @class Fragment
##
@dataclass
class Fragment:
    text: str
    color: int
    type: str


# TODO
@dataclass
class CacheEntry:
    path: list
    chars: int
