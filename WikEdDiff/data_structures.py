#! /usr/bin/env python3

"""
Main data structures used in the WikEdDiff class. In the original JavaScript
code they were represented as plain tables, but in Python we need to create
custom objects.

See diff.py for documentation.
"""

from namedlist import namedlist


##
## Token element.
##
## @class Token
##
Token = namedlist("Token", ["token",
                            "prev",
                            "next",
                            "link",
                            "number",
                            "unique",
                           ])

##
## Symbols table.
##
## @class Symbols
##
Symbols = namedlist("Symbols", ["token",
                                "hashTable",
                                "linked",
                               ])

##
## Symbol element.
##
## @class Symbol
##
Symbol = namedlist("Symbol", ["newCount",
                              "oldCount",
                              "newToken",
                              "oldToken",
                             ])

##
## Gap element.
##
## @class Gap
##
Gap = namedlist("Gap", ["newFirst",
                        "newLast",
                        "newTokens",
                        "oldFirst",
                        "oldLast",
                        "oldTokens",
                        "charSplit",
                       ])

##
## Block element.
##
## @class Block
##
Block = namedlist("Block", ["oldBlock",
                            "newBlock",
                            "oldNumber",
                            "newNumber",
                            "oldStart",
                            "count",
                            "unique",
                            "words",
                            "chars",
                            "type",
                            "section",
                            "group",
                            "fixed",
                            "moved",
                            "text",
                           ], use_slots=False)
# FIXME: use_slots=False should be removed (depends on https://bitbucket.org/ericvsmith/namedlist/issues/26/none-private-default-fields )

##
## Section element.
##
## @class Section
##
Section = namedlist("Section", ["blockStart",
                                "blockEnd",
                               ])


##
## Group element.
##
## @class Group
##
Group = namedlist("Group", ["oldNumber",
                            "blockStart",
                            "blockEnd",
                            "unique",
                            "maxWords",
                            "words",
                            "chars",
                            "fixed",
                            "movedFrom",
                            "color",
                           ])


##
## Fragment element.
##
## @class Fragment
##
Fragment = namedlist("Fragment", ["text",
                                  "color",
                                  "type",
                                 ])

# TODO
CacheEntry = namedlist("CacheEntry", ["path",
                                      "chars",
                                     ])
