#! /usr/bin/env python3

"""
WikEdDiff is a visual inline-style difference engine with block move support.

The original wikEdDiff is an improved JavaScript diff library that returns
html/css-formatted new text version with highlighted deletions, insertions,
and block moves. It is also available as a MediaWiki extension, which is a
one-to-one synced port with changes and fixes applied to both versions.

 - JavaScript library (mirror): https://en.wikipedia.org/wiki/User:Cacycle/diff
 - JavaScript online tool: http://cacycle.altervista.org/wikEd-diff-tool.html
 - MediaWiki extension: https://www.mediawiki.org/wiki/Extension:wikEdDiff

python-wikeddiff is a port of the original JavaScript library to Python. There
were no changes to the algorithm, so all credits go to the original author,
Cacycle. The following metadata were attached to the diff.js file, which served
as the base for the port:

    @name        wikEd diff
    @version     1.2.4
    @date        October 23, 2014
    @description improved word-based diff library with block move detection
    @homepage    https://en.wikipedia.org/wiki/User:Cacycle/diff
    @source      https://en.wikipedia.org/wiki/User:Cacycle/diff.js
    @author      Cacycle (https://en.wikipedia.org/wiki/User:Cacycle)
    @license     released into the public domain


WikEdDiff applies a word-based algorithm that uses unique words as anchor points
to identify matching text and moved blocks (Paul Heckel: A technique for
isolating differences between files. Communications of the ACM 21(4):264 (1978)).

Additional features:

 - Visual inline style, changes are shown in a single output text
 - Block move detection and highlighting
 - Resolution down to characters level
 - Unicode and multilingual support
 - Stepwise split (paragraphs, lines, sentences, words, characters)
 - Recursive diff
 - Optimized code for resolving unmatched sequences
 - Minimization of length of moved blocks
 - Alignment of ambiguous unmatched sequences to next line break or word border
 - Clipping of unchanged irrelevant parts from the output (optional)
 - Fully customizable
 - Text split optimized for MediaWiki source texts
 - Well commented and documented code

Datastructures (abbreviations from publication):

class WikEdDiffText:  diff text object (new or old version)
  .text                 text of version
  .words[]              word count table
  .first                index of first token in tokens list
  .last                 index of last token in tokens list

  .tokens[]:          token list for new or old string (doubly-linked list) (N and O)
    .prev               previous list item
    .next               next list item
    .token              token string
    .link               index of corresponding token in new or old text (OA and NA)
    .number             list enumeration number
    .unique             token is unique word in text

class WikEdDiff:      diff object
  .config[]:            configuration settings, see top of code for customization options
     .regExp[]:            all regular expressions
         .split             regular expressions used for splitting text into tokens
     .htmlCode            HTML code fragments used for creating the output
     .msg                 output messages
  .newText              new text
  .oldText              old text
  .maxWords             word count of longest linked block
  .html                 diff html
  .error                flag: result has not passed unit tests
  .bordersDown[]        linked region borders downwards, [new index, old index]
  .bordersUp[]          linked region borders upwards, [new index, old index]
  .symbols:             symbols table for whole text at all refinement levels
    .token[]              hash table of parsed tokens for passes 1 - 3, points to symbol[i]
    .symbol[]:            array of objects that hold token counters and pointers:
      .newCount             new text token counter (NC)
      .oldCount             old text token counter (OC)
      .newToken             token index in text.newText.tokens
      .oldToken             token index in text.oldText.tokens
    .linked               flag: at least one unique token pair has been linked

  .blocks[]:            array, block data (consecutive text tokens) in new text order
    .oldBlock             number of block in old text order
    .newBlock             number of block in new text order
    .oldNumber            old text token number of first token
    .newNumber            new text token number of first token
    .oldStart             old text token index of first token
    .count                number of tokens
    .unique               contains unique linked token
    .words                word count
    .chars                char length
    .type                 '=', '-', '+', '|' (same, deletion, insertion, mark)
    .section              section number
    .group                group number of block
    .fixed                belongs to a fixed (not moved) group
    .moved                moved block group number corresponding with mark block
    .text                 text of block tokens

  .sections[]:          array, block sections with no block move crosses outside a section
    .blockStart           first block in section
    .blockEnd             last block in section

  .groups[]:            array, section blocks that are consecutive in old text order
    .oldNumber            first block oldNumber
    .blockStart           first block index
    .blockEnd             last block index
    .unique               contains unique linked token
    .maxWords             word count of longest linked block
    .words                word count
    .chars                char count
    .fixed                not moved from original position
    .movedFrom            group position this group has been moved from
    .color                color number of moved group

  .fragments[]:         diff fragment list ready for markup, abstraction layer for customization
    .text                 block or mark text
    .color                moved block or mark color number
    .type                 '=', '-', '+'   same, deletion, insertion
                          '<', '>'        mark left, mark right
                          '(<', '(>', ')' block start and end
                          '~', ' ~', '~ ' omission indicators
                          '[', ']', ','   fragment start and end, fragment separator
                          '{', '}'        container start and end
"""

import re
import time
import itertools
import copy
import logging

from namedlist import namedlist

logger = logging.getLogger(__name__)


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


# Configuration and customization settings.
class WikedDiffConfig:
    # Core diff settings (with default values).

    ##
    ## @var bool config.fullDiff
    ##   Show complete un-clipped diff text (False)
    ##
    fullDiff = False

    ##
    ## @var bool config.showBlockMoves
    ##   Enable block move layout with highlighted blocks and marks at the original positions (True)
    ##
    showBlockMoves = True

    ##
    ## @var bool config.charDiff
    ##   Enable character-refined diff (True)
    ##
    charDiff = True

    ##
    ## @var bool config.repeatedDiff
    ##   Enable repeated diff to resolve problematic sequences (True)
    ##
    repeatedDiff = True

    ##
    ## @var bool config.recursiveDiff
    ##   Enable recursive diff to resolve problematic sequences (True)
    ##
    recursiveDiff = True

    ##
    ## @var int config.recursionMax
    ##   Maximum recursion depth (10)
    ##
    recursionMax = 10

    ##
    ## @var bool config.unlinkBlocks
    ##   Reject blocks if they are too short and their words are not unique,
    ##   prevents fragmentated diffs for very different versions (True)
    ##
    unlinkBlocks = True

    ##
    ## @var int config.unlinkMax
    ##   Maximum number of rejection cycles (5)
    ##
    unlinkMax = 5

    ##
    ## @var int config.blockMinLength
    ##   Reject blocks if shorter than this number of real words (3)
    ##
    blockMinLength = 3

    ##
    ## @var bool config.coloredBlocks
    ##   Display blocks in differing colors (rainbow color scheme) (False)
    ##
#    coloredBlocks = False
    coloredBlocks = True

    ##
    ## @var bool config.coloredBlocks
    ##   Do not use UniCode block move marks (legacy browsers) (False)
    ##
    noUnicodeSymbols = False

    ##
    ## @var bool config.stripTrailingNewline
    ##   Strip trailing newline off of texts (True in .js, False in .php)
    ##
    stripTrailingNewline = True

    ##
    ## @var bool config.debug
    ##   Show debug infos and stats (block, group, and fragment data) in debug console (False)
    ##
    debug = False

    ##
    ## @var bool config.timer
    ##   Show timing results in debug console (False)
    ##
    timer = False

    ##
    ## @var bool config.unitTesting
    ##   Run unit tests to prove correct working, display results in debug console (False)
    ##
    unitTesting = False

    # RegExp character classes.

    # UniCode letter support for regexps
    # From http://xregexp.com/addons/unicode/unicode-base.js v1.0.0
    regExpLetters = 'a-zA-Z0-9' + re.sub("(\w{4})", "\\u\g<1>",
                    '00AA00B500BA00C0-00D600D8-00F600F8-02C102C6-02D102E0-02E402EC02EE0370-037403760377037A-' + \
                    '037D03860388-038A038C038E-03A103A3-03F503F7-0481048A-05270531-055605590561-058705D0-05EA' + \
                    '05F0-05F20620-064A066E066F0671-06D306D506E506E606EE06EF06FA-06FC06FF07100712-072F074D-' + \
                    '07A507B107CA-07EA07F407F507FA0800-0815081A082408280840-085808A008A2-08AC0904-0939093D' + \
                    '09500958-09610971-09770979-097F0985-098C098F09900993-09A809AA-09B009B209B6-09B909BD09CE' + \
                    '09DC09DD09DF-09E109F009F10A05-0A0A0A0F0A100A13-0A280A2A-0A300A320A330A350A360A380A39' + \
                    '0A59-0A5C0A5E0A72-0A740A85-0A8D0A8F-0A910A93-0AA80AAA-0AB00AB20AB30AB5-0AB90ABD0AD00AE0' + \
                    '0AE10B05-0B0C0B0F0B100B13-0B280B2A-0B300B320B330B35-0B390B3D0B5C0B5D0B5F-0B610B710B83' + \
                    '0B85-0B8A0B8E-0B900B92-0B950B990B9A0B9C0B9E0B9F0BA30BA40BA8-0BAA0BAE-0BB90BD00C05-0C0C' + \
                    '0C0E-0C100C12-0C280C2A-0C330C35-0C390C3D0C580C590C600C610C85-0C8C0C8E-0C900C92-0CA80CAA-' + \
                    '0CB30CB5-0CB90CBD0CDE0CE00CE10CF10CF20D05-0D0C0D0E-0D100D12-0D3A0D3D0D4E0D600D610D7A-' + \
                    '0D7F0D85-0D960D9A-0DB10DB3-0DBB0DBD0DC0-0DC60E01-0E300E320E330E40-0E460E810E820E840E87' + \
                    '0E880E8A0E8D0E94-0E970E99-0E9F0EA1-0EA30EA50EA70EAA0EAB0EAD-0EB00EB20EB30EBD0EC0-0EC4' + \
                    '0EC60EDC-0EDF0F000F40-0F470F49-0F6C0F88-0F8C1000-102A103F1050-1055105A-105D106110651066' + \
                    '106E-10701075-1081108E10A0-10C510C710CD10D0-10FA10FC-1248124A-124D1250-12561258125A-125D' + \
                    '1260-1288128A-128D1290-12B012B2-12B512B8-12BE12C012C2-12C512C8-12D612D8-13101312-1315' + \
                    '1318-135A1380-138F13A0-13F41401-166C166F-167F1681-169A16A0-16EA1700-170C170E-17111720-' + \
                    '17311740-17511760-176C176E-17701780-17B317D717DC1820-18771880-18A818AA18B0-18F51900-191C' + \
                    '1950-196D1970-19741980-19AB19C1-19C71A00-1A161A20-1A541AA71B05-1B331B45-1B4B1B83-1BA0' + \
                    '1BAE1BAF1BBA-1BE51C00-1C231C4D-1C4F1C5A-1C7D1CE9-1CEC1CEE-1CF11CF51CF61D00-1DBF1E00-1F15' + \
                    '1F18-1F1D1F20-1F451F48-1F4D1F50-1F571F591F5B1F5D1F5F-1F7D1F80-1FB41FB6-1FBC1FBE1FC2-1FC4' + \
                    '1FC6-1FCC1FD0-1FD31FD6-1FDB1FE0-1FEC1FF2-1FF41FF6-1FFC2071207F2090-209C21022107210A-2113' + \
                    '21152119-211D212421262128212A-212D212F-2139213C-213F2145-2149214E218321842C00-2C2E2C30-' + \
                    '2C5E2C60-2CE42CEB-2CEE2CF22CF32D00-2D252D272D2D2D30-2D672D6F2D80-2D962DA0-2DA62DA8-2DAE' + \
                    '2DB0-2DB62DB8-2DBE2DC0-2DC62DC8-2DCE2DD0-2DD62DD8-2DDE2E2F300530063031-3035303B303C3041-' + \
                    '3096309D-309F30A1-30FA30FC-30FF3105-312D3131-318E31A0-31BA31F0-31FF3400-4DB54E00-9FCC' + \
                    'A000-A48CA4D0-A4FDA500-A60CA610-A61FA62AA62BA640-A66EA67F-A697A6A0-A6E5A717-A71FA722-' + \
                    'A788A78B-A78EA790-A793A7A0-A7AAA7F8-A801A803-A805A807-A80AA80C-A822A840-A873A882-A8B3' + \
                    'A8F2-A8F7A8FBA90A-A925A930-A946A960-A97CA984-A9B2A9CFAA00-AA28AA40-AA42AA44-AA4BAA60-' + \
                    'AA76AA7AAA80-AAAFAAB1AAB5AAB6AAB9-AABDAAC0AAC2AADB-AADDAAE0-AAEAAAF2-AAF4AB01-AB06AB09-' + \
                    'AB0EAB11-AB16AB20-AB26AB28-AB2EABC0-ABE2AC00-D7A3D7B0-D7C6D7CB-D7FBF900-FA6DFA70-FAD9' + \
                    'FB00-FB06FB13-FB17FB1DFB1F-FB28FB2A-FB36FB38-FB3CFB3EFB40FB41FB43FB44FB46-FBB1FBD3-FD3D' + \
                    'FD50-FD8FFD92-FDC7FDF0-FDFBFE70-FE74FE76-FEFCFF21-FF3AFF41-FF5AFF66-FFBEFFC2-FFC7FFCA-' + \
                    'FFCFFFD2-FFD7FFDA-FFDC'
            )

    # New line characters without and with \n and \r
    regExpNewLines = '\\u0085\\u2028'
    regExpNewLinesAll = '\\n\\r\\u0085\\u2028'

    # Breaking white space characters without \n, \r, and \f
    regExpBlanks = ' \\t\\x0b\\u2000-\\u200b\\u202f\\u205f\\u3000'

    # Full stops without '.'
    regExpFullStops = \
            '\\u0589\\u06D4\\u0701\\u0702\\u0964\\u0DF4\\u1362\\u166E\\u1803\\u1809' + \
            '\\u2CF9\\u2CFE\\u2E3C\\u3002\\uA4FF\\uA60E\\uA6F3\\uFE52\\uFF0E\\uFF61'

    # New paragraph characters without \n and \r
    regExpNewParagraph = '\\f\\u2029'

    # Exclamation marks without '!'
    regExpExclamationMarks = \
            '\\u01C3\\u01C3\\u01C3\\u055C\\u055C\\u07F9\\u1944\\u1944' + \
            '\\u203C\\u203C\\u2048\\u2048\\uFE15\\uFE57\\uFF01'

    # Question marks without '?'
    regExpQuestionMarks = \
            '\\u037E\\u055E\\u061F\\u1367\\u1945\\u2047\\u2049' + \
            '\\u2CFA\\u2CFB\\u2E2E\\uA60F\\uA6F7\\uFE56\\uFF1F'

    # Clip settings.

    # Find clip position: characters from right
    clipHeadingLeft =      1500
    clipParagraphLeftMax = 1500
    clipParagraphLeftMin =  500
    clipLineLeftMax =      1000
    clipLineLeftMin =       500
    clipBlankLeftMax =     1000
    clipBlankLeftMin =      500
    clipCharsLeft =         500

    # Find clip position: characters from right
    clipHeadingRight =      1500
    clipParagraphRightMax = 1500
    clipParagraphRightMin =  500
    clipLineRightMax =      1000
    clipLineRightMin =       500
    clipBlankRightMax =     1000
    clipBlankRightMin =      500
    clipCharsRight =         500

    # Maximum number of lines to search for clip position
    clipLinesRightMax = 10
    clipLinesLeftMax = 10

    # Skip clipping if ranges are too close
    clipSkipLines = 5
    clipSkipChars = 1000

    # Css stylesheet
    cssMarkLeft = '◀'
    cssMarkRight = '▶'
    stylesheet = """
/* Insert */
.wikEdDiffInsert {
    font-weight: bold; background-color: #bbddff;
    color: #222; border-radius: 0.25em; padding: 0.2em 1px;
}
.wikEdDiffInsertBlank { background-color: #66bbff; }
.wikEdDiffFragment:hover .wikEdDiffInsertBlank { background-color: #bbddff; }

/* Delete */
.wikEdDiffDelete {
    font-weight: bold; background-color: #ffe49c;
    color: #222; border-radius: 0.25em; padding: 0.2em 1px;
}
.wikEdDiffDeleteBlank { background-color: #ffd064; }
.wikEdDiffFragment:hover .wikEdDiffDeleteBlank { background-color: #ffe49c; }

/* Block */
.wikEdDiffBlock {
    font-weight: bold; background-color: #e8e8e8;
    border-radius: 0.25em; padding: 0.2em 1px; margin: 0 1px;
}
.wikEdDiffBlock { }
.wikEdDiffBlock0 { background-color: #ffff80; }
.wikEdDiffBlock1 { background-color: #d0ff80; } 
.wikEdDiffBlock2 { background-color: #ffd8f0; } 
.wikEdDiffBlock3 { background-color: #c0ffff; } 
.wikEdDiffBlock4 { background-color: #fff888; } 
.wikEdDiffBlock5 { background-color: #bbccff; } 
.wikEdDiffBlock6 { background-color: #e8c8ff; } 
.wikEdDiffBlock7 { background-color: #ffbbbb; } 
.wikEdDiffBlock8 { background-color: #a0e8a0; } 
.wikEdDiffBlockHighlight {
    background-color: #777; color: #fff; 
    border: solid #777; border-width: 1px 0; 
} 

/* Mark */
.wikEdDiffMarkLeft, .wikEdDiffMarkRight {
    font-weight: bold; background-color: #ffe49c; 
    color: #666; border-radius: 0.25em; padding: 0.2em; margin: 0 1px; 
} 
.wikEdDiffMarkLeft:before { content: "{cssMarkLeft}"; } 
.wikEdDiffMarkRight:before { content: "{cssMarkRight}"; } 
.wikEdDiffMarkLeft.wikEdDiffNoUnicode:before { content: "<"; } 
.wikEdDiffMarkRight.wikEdDiffNoUnicode:before { content: ">"; } 
.wikEdDiffMark { background-color: #e8e8e8; color: #666; } 
.wikEdDiffMark0 { background-color: #ffff60; } 
.wikEdDiffMark1 { background-color: #c8f880; } 
.wikEdDiffMark2 { background-color: #ffd0f0; } 
.wikEdDiffMark3 { background-color: #a0ffff; } 
.wikEdDiffMark4 { background-color: #fff860; } 
.wikEdDiffMark5 { background-color: #b0c0ff; } 
.wikEdDiffMark6 { background-color: #e0c0ff; } 
.wikEdDiffMark7 { background-color: #ffa8a8; } 
.wikEdDiffMark8 { background-color: #98e898; } 
.wikEdDiffMarkHighlight { background-color: #777; color: #fff; } 

/* Wrappers */
.wikEdDiffContainer { } 
.wikEdDiffFragment {
    white-space: pre-wrap; background: #fff; border: #bbb solid; 
    border-width: 1px 1px 1px 0.5em; border-radius: 0.5em; font-family: sans-serif; 
    font-size: 88%; line-height: 1.6; box-shadow: 2px 2px 2px #ddd; padding: 1em; margin: 0; 
} 
.wikEdDiffNoChange {
    background: #f0f0f0; border: 1px #bbb solid; border-radius: 0.5em; 
    line-height: 1.6; box-shadow: 2px 2px 2px #ddd; padding: 0.5em; margin: 1em 0; 
    text-align: center; 
} 
.wikEdDiffSeparator { margin-bottom: 1em; } 
.wikEdDiffOmittedChars { } 

/* Newline */
.wikEdDiffNewline:before { content: "¶"; color: transparent; } 
.wikEdDiffBlock:hover .wikEdDiffNewline:before { color: #aaa; } 
.wikEdDiffBlockHighlight .wikEdDiffNewline:before { color: transparent; } 
.wikEdDiffBlockHighlight:hover .wikEdDiffNewline:before { color: #ccc; } 
.wikEdDiffBlockHighlight:hover .wikEdDiffInsert .wikEdDiffNewline:before, 
.wikEdDiffInsert:hover .wikEdDiffNewline:before
{ color: #999; } 
.wikEdDiffBlockHighlight:hover .wikEdDiffDelete .wikEdDiffNewline:before, 
.wikEdDiffDelete:hover .wikEdDiffNewline:before
{ color: #aaa; } 

/* Tab */
.wikEdDiffTab { position: relative; } 
.wikEdDiffTabSymbol { position: absolute; top: -0.2em; } 
.wikEdDiffTabSymbol:before { content: "→"; font-size: smaller; color: #ccc; } 
.wikEdDiffBlock .wikEdDiffTabSymbol:before { color: #aaa; } 
.wikEdDiffBlockHighlight .wikEdDiffTabSymbol:before { color: #aaa; } 
.wikEdDiffInsert .wikEdDiffTabSymbol:before { color: #aaa; } 
.wikEdDiffDelete .wikEdDiffTabSymbol:before { color: #bbb; } 

/* Space */
.wikEdDiffSpace { position: relative; } 
.wikEdDiffSpaceSymbol { position: absolute; top: -0.2em; left: -0.05em; } 
.wikEdDiffSpaceSymbol:before { content: "·"; color: transparent; } 
.wikEdDiffBlock:hover .wikEdDiffSpaceSymbol:before { color: #999; } 
.wikEdDiffBlockHighlight .wikEdDiffSpaceSymbol:before { color: transparent; } 
.wikEdDiffBlockHighlight:hover .wikEdDiffSpaceSymbol:before { color: #ddd; } 
.wikEdDiffBlockHighlight:hover .wikEdDiffInsert .wikEdDiffSpaceSymbol:before,
.wikEdDiffInsert:hover .wikEdDiffSpaceSymbol:before 
{ color: #888; } 
.wikEdDiffBlockHighlight:hover .wikEdDiffDelete .wikEdDiffSpaceSymbol:before,
.wikEdDiffDelete:hover .wikEdDiffSpaceSymbol:before 
{ color: #999; } 

/* Error */
.wikEdDiffError .wikEdDiffFragment,
.wikEdDiffError .wikEdDiffNoChange
{ background: #faa; }
"""

    # Regular expressions to configuration settings.
    regExp = dotdictify({
        # RegExps for splitting text
        'split': {

                # Split into paragraphs, after double newlines
                'paragraph': re.compile(
                        '(\\r\\n|\\n|\\r){2,}|[' +
                        regExpNewParagraph +
                        ']',
                        re.MULTILINE
                ),

                # Split into lines
                'line': re.compile(
                        '\\r\\n|\\n|\\r|[' +
                        regExpNewLinesAll +
                        ']',
                        re.MULTILINE
                ),

                # Split into sentences /[^ ].*?[.!?:;]+(?= |$)/
                'sentence': re.compile(
                        '[^' +
                        regExpBlanks +
                        '].*?[.!?:;' +
                        regExpFullStops +
                        regExpExclamationMarks +
                        regExpQuestionMarks +
                        ']+(?=[' +
                        regExpBlanks +
                        ']|$)',
                        re.MULTILINE
                ),

                # Split into inline chunks
                'chunk': re.compile(
                        '\\[\\[[^\\[\\]\\n]+\\]\\]|' +       # [[wiki link]]
                        '\\{\\{[^\\{\\}\\n]+\\}\\}|' +       # {{template}}
                        '\\[[^\\[\\]\\n]+\\]|' +             # [ext. link]
                        '<\\/?[^<>\\[\\]\\{\\}\\n]+>|' +     # <html>
                        '\\[\\[[^\\[\\]\\|\\n]+\\]\\]\\||' + # [[wiki link|
                        '\\{\\{[^\\{\\}\\|\\n]+\\||' +       # {{template|
                        '\\b((https?:|)\\/\\/)[^\\x00-\\x20\\s"\\[\\]\\x7f]+', # link
                        re.MULTILINE
                ),

                # Split into words, multi-char markup, and chars
                # regExpLetters speed-up: \\w+
                'word': re.compile(
                        '(\\w+|[_' +
                        regExpLetters +
                        '])+([\'’][_' +
                        regExpLetters +
                        ']*)*|\\[\\[|\\]\\]|\\{\\{|\\}\\}|&\\w+;|\'\'\'|\'\'|==+|\\{\\||\\|\\}|\\|-|.',
                        re.MULTILINE
                ),

                # Split into chars
                'character': re.compile( ".", re.MULTILINE | re.DOTALL ),
        },

        # RegExp to detect blank tokens
        'blankOnlyToken': re.compile(
                '[^' +
                regExpBlanks +
                regExpNewLinesAll +
                regExpNewParagraph +
                ']'
        ),

        # RegExps for sliding gaps: newlines and space/word breaks
        'slideStop': re.compile(
                '[' +
                regExpNewLinesAll +
                regExpNewParagraph +
                ']$'
        ),
        'slideBorder': re.compile(
                '[' +
                regExpBlanks +
                ']$'
        ),

        # RegExps for counting words
        'countWords': re.compile(
                '(\\w+|[_' +
                regExpLetters +
                '])+([\'’][_' +
                regExpLetters +
                ']*)*',
                re.MULTILINE
        ),
        'countChunks': re.compile(
                '\\[\\[[^\\[\\]\\n]+\\]\\]|' +       # [[wiki link]]
                '\\{\\{[^\\{\\}\\n]+\\}\\}|' +       # {{template}}
                '\\[[^\\[\\]\\n]+\\]|' +             # [ext. link]
                '<\\/?[^<>\\[\\]\\{\\}\\n]+>|' +     # <html>
                '\\[\\[[^\\[\\]\\|\\n]+\\]\\]\\||' + # [[wiki link|
                '\\{\\{[^\\{\\}\\|\\n]+\\||' +       # {{template|
                '\\b((https?:|)\\/\\/)[^\\x00-\\x20\\s"\\[\\]\\x7f]+', # link
                re.MULTILINE
        ),

        # RegExp detecting blank-only and single-char blocks
        'blankBlock': re.compile( "^([^\t\S]+|[^\t])$", re.MULTILINE ),

        # RegExps for clipping
        'clipLine': re.compile(
                '[' + regExpNewLinesAll +
                regExpNewParagraph +
                ']+',
                re.MULTILINE
        ),
        'clipHeading': re.compile(
                '( ^|\\n)(==+.+?==+|\\{\\||\\|\\}).*?(?=\\n|$)', re.MULTILINE ),
        'clipParagraph': re.compile(
                '( (\\r\\n|\\n|\\r){2,}|[' +
                regExpNewParagraph +
                '])+',
                re.MULTILINE
        ),
        'clipBlank': re.compile(
                '[' +
                regExpBlanks + ']+',
                re.MULTILINE
        ),
        'clipTrimNewLinesLeft': re.compile(
                '[' +
                regExpNewLinesAll +
                regExpNewParagraph +
                ']+$'
        ),
        'clipTrimNewLinesRight': re.compile(
                '^[' +
                regExpNewLinesAll +
                regExpNewParagraph +
                ']+'
        ),
        'clipTrimBlanksLeft': re.compile(
                '[' +
                regExpBlanks +
                regExpNewLinesAll +
                regExpNewParagraph +
                ']+$'
        ),
        'clipTrimBlanksRight': re.compile(
                '^[' +
                regExpBlanks +
                regExpNewLinesAll +
                regExpNewParagraph +
                ']+'
        )
    })

    # Messages.
    msg = dotdictify({
            'wiked-diff-empty': '(No difference)',
            'wiked-diff-same':  '=',
            'wiked-diff-ins':   '+',
            'wiked-diff-del':   '-',
            'wiked-diff-block-left':  '◀',
            'wiked-diff-block-right': '▶',
            'wiked-diff-block-left-nounicode':  '<',
            'wiked-diff-block-right-nounicode': '>',
            'wiked-diff-error': 'Error: diff not consistent with versions!'
    })

    ##
    ## Output html fragments.
    ## Dynamic replacements:
    ##   {number}: class/color/block/mark/id number
    ##   {title}: title attribute (popup)
    ##   {nounicode}: noUnicodeSymbols fallback
    ##
    htmlCode = dotdictify({
        'noChangeStart':
                '<div class="wikEdDiffNoChange" title="' +
                msg['wiked-diff-same'] +
                '">',
        'noChangeEnd': '</div>',

        'containerStart': '<div class="wikEdDiffContainer" id="wikEdDiffContainer">',
        'containerEnd': '</div>',

        'fragmentStart': '<pre class="wikEdDiffFragment" style="white-space: pre-wrap;">',
        'fragmentEnd': '</pre>',
        'separator': '<div class="wikEdDiffSeparator"></div>',

        'insertStart':
                '<span class="wikEdDiffInsert" title="' +
                msg['wiked-diff-ins'] +
                '">',
        'insertStartBlank':
                '<span class="wikEdDiffInsert wikEdDiffInsertBlank" title="' +
                msg['wiked-diff-ins'] +
                '">',
        'insertEnd': '</span>',

        'deleteStart':
                '<span class="wikEdDiffDelete" title="' +
                msg['wiked-diff-del'] +
                '">',
        'deleteStartBlank':
                '<span class="wikEdDiffDelete wikEdDiffDeleteBlank" title="' +
                msg['wiked-diff-del'] +
                '">',
        'deleteEnd': '</span>',

        'blockStart':
                '<span class="wikEdDiffBlock"' +
                'title="{title}" id="wikEdDiffBlock{number}"' +
                'onmouseover="wikEdDiffBlockHandler(undefined, this, \'mouseover\');">',
        'blockColoredStart':
                '<span class="wikEdDiffBlock wikEdDiffBlock wikEdDiffBlock{number}"' +
                'title="{title}" id="wikEdDiffBlock{number}"' +
                'onmouseover="wikEdDiffBlockHandler(undefined, this, \'mouseover\');">',
        'blockEnd': '</span>',

        'markLeft':
                '<span class="wikEdDiffMarkLeft{nounicode}"' +
                'title="{title}" id="wikEdDiffMark{number}"' +
                'onmouseover="wikEdDiffBlockHandler(undefined, this, \'mouseover\');"></span>',
        'markLeftColored':
                '<span class="wikEdDiffMarkLeft{nounicode} wikEdDiffMark wikEdDiffMark{number}"' +
                'title="{title}" id="wikEdDiffMark{number}"' +
                'onmouseover="wikEdDiffBlockHandler(undefined, this, \'mouseover\');"></span>',

        'markRight':
                '<span class="wikEdDiffMarkRight{nounicode}"' +
                'title="{title}" id="wikEdDiffMark{number}"' +
                'onmouseover="wikEdDiffBlockHandler(undefined, this, \'mouseover\');"></span>',
        'markRightColored':
                '<span class="wikEdDiffMarkRight{nounicode} wikEdDiffMark wikEdDiffMark{number}"' +
                'title="{title}" id="wikEdDiffMark{number}"' +
                'onmouseover="wikEdDiffBlockHandler(undefined, this, \'mouseover\');"></span>',

        'newline': '<span class="wikEdDiffNewline">\n</span>',
        'tab': '<span class="wikEdDiffTab"><span class="wikEdDiffTabSymbol"></span>\t</span>',
        'space': '<span class="wikEdDiffSpace"><span class="wikEdDiffSpaceSymbol"></span> </span>',

        'omittedChars': '<span class="wikEdDiffOmittedChars">…</span>',

        'errorStart': '<div class="wikEdDiffError" title="Error: diff not consistent with versions!">',
        'errorEnd': '</div>'
    })

##
## wikEd diff main class.
##
## @class WikEdDiff
##
class WikEdDiff:

    ##
    ## Constructor, initialize settings.
    ##
    ## @param[in] object wikEdDiffConfig Custom customization settings
    ## @param[out] object config Settings
    ##
    def __init__(self, config):

        self.config = config

        # Internal data structures.

        # @var WikEdDiffText newText New text version object with text and token list
        self.newText = None;

        # @var WikEdDiffText oldText Old text version object with text and token list
        self.oldText = None;

        # @var Symbols symbols Symbols table for whole text at all refinement levels
        self.symbols = Symbols(token=[], hashTable={}, linked=False)

        # @var array bordersDown Matched region borders downwards
        self.bordersDown = [];

        # @var array bordersUp Matched region borders upwards
        self.bordersUp = [];

        # @var array blocks Block data (consecutive text tokens) in new text order
        self.blocks = [];

        # @var int maxWords Maximal detected word count of all linked blocks
        self.maxWords = 0;

        # @var array groups Section blocks that are consecutive in old text order
        self.groups = [];

        # @var array sections Block sections with no block move crosses outside a section
        self.sections = [];

        # @var object timer Debug timer array: string 'label' => float milliseconds.
        self.timer = {};

        # @var array recursionTimer Count time spent in recursion level in milliseconds.
        self.recursionTimer = {}

        # Output data.

        # @var bool error Unit tests have detected a diff error
        self.error = False;

        # @var array fragments Diff fragment list for markup, abstraction layer for customization
        self.fragments = [];

        # @var string html Html code of diff
        self.html = '';


    ##
    ## Main diff method.
    ##
    ## @param string oldString Old text version
    ## @param string newString New text version
    ## @param[out] array fragment
    ##   Diff fragment list ready for markup, abstraction layer for customized diffs
    ## @param[out] string html Html code of diff
    ## @return string Html code of diff
    ##
    def diff( self, oldString, newString ):

        if self.config.timer is True:
            # Start total timer
            self.time( 'total' );
            # Start diff timer
            self.time( 'diff' );

        # Reset error flag
        self.error = False

        # Strip trailing newline (.js only)
        if self.config.stripTrailingNewline is True:
            if newString[ -1 ] == '\n' and oldString[ -1 ] == '\n':
                newString = newString[:-1]
                oldString = oldString[:-1]

        # Load version strings into WikEdDiffText objects
        self.newText = WikEdDiffText( newString, self )
        self.oldText = WikEdDiffText( oldString, self )

        # Trap trivial changes: no change
        if self.newText.text == self.oldText.text:
            self.html = self.config.htmlCode.containerStart + \
                        self.config.htmlCode.noChangeStart + \
                        self.htmlEscape( self.config.msg['wiked-diff-empty'] ) + \
                        self.config.htmlCode.noChangeEnd + \
                        self.config.htmlCode.containerEnd;
            return self.html

        # Trap trivial changes: old text deleted
        if self.oldText.text == '' or ( self.oldText.text == '\n' and self.newText.text[ len(self.newText.text) - 1 ] == '\n' ):
            self.html = self.config.htmlCode.containerStart + \
                        self.config.htmlCode.fragmentStart + \
                        self.config.htmlCode.insertStart + \
                        self.htmlEscape( self.newText.text ) + \
                        self.config.htmlCode.insertEnd + \
                        self.config.htmlCode.fragmentEnd + \
                        self.config.htmlCode.containerEnd;
            return self.html

        # Trap trivial changes: new text deleted
        if self.newText.text == '' or ( self.newText.text == '\n' and self.oldText.text[ len(self.oldText.text) - 1 ] == '\n' ):
            self.html = self.config.htmlCode.containerStart + \
                        self.config.htmlCode.fragmentStart + \
                        self.config.htmlCode.deleteStart + \
                        self.htmlEscape( self.oldText.text ) + \
                        self.config.htmlCode.deleteEnd + \
                        self.config.htmlCode.fragmentEnd + \
                        self.config.htmlCode.containerEnd;
            return self.html;

        # Split new and old text into paragraps
        if self.config.timer is True:
            self.time( 'paragraph split' );
        self.newText.splitText( 'paragraph' );
        self.oldText.splitText( 'paragraph' );
        if self.config.timer is True:
            self.timeEnd( 'paragraph split' );

        # Calculate diff
        self.calculateDiff( 'line' );

        # Refine different paragraphs into lines
        if self.config.timer is True:
            self.time( 'line split' );
        self.newText.splitRefine( 'line' );
        self.oldText.splitRefine( 'line' );
        if self.config.timer is True:
            self.timeEnd( 'line split' );

        # Calculate refined diff
        self.calculateDiff( 'line' );

        # Refine different lines into sentences
        if self.config.timer is True:
            self.time( 'sentence split' );
        self.newText.splitRefine( 'sentence' );
        self.oldText.splitRefine( 'sentence' );
        if self.config.timer is True:
            self.timeEnd( 'sentence split' );

        # Calculate refined diff
        self.calculateDiff( 'sentence' );

        # Refine different sentences into chunks
        if self.config.timer is True:
            self.time( 'chunk split' );
        self.newText.splitRefine( 'chunk' );
        self.oldText.splitRefine( 'chunk' );
        if self.config.timer is True:
            self.timeEnd( 'chunk split' );

        # Calculate refined diff
        self.calculateDiff( 'chunk' );

        # Refine different chunks into words
        if self.config.timer is True:
            self.time( 'word split' );
        self.newText.splitRefine( 'word' );
        self.oldText.splitRefine( 'word' );
        if self.config.timer is True:
            self.timeEnd( 'word split' );

        # Calculate refined diff information with recursion for unresolved gaps
        self.calculateDiff( 'word', True );

        # Slide gaps
        if self.config.timer is True:
            self.time( 'word slide' );
        self.slideGaps( self.newText, self.oldText );
        self.slideGaps( self.oldText, self.newText );
        if self.config.timer is True:
            self.timeEnd( 'word slide' );

        # Split tokens into chars
        if self.config.charDiff is True:
            # Split tokens into chars in selected unresolved gaps
            if self.config.timer is True:
                self.time( 'character split' );
            self.splitRefineChars();
            if self.config.timer is True:
                self.timeEnd( 'character split' );

            # Calculate refined diff information with recursion for unresolved gaps
            self.calculateDiff( 'character', True );

            # Slide gaps
            if self.config.timer is True:
                self.time( 'character slide' );
            self.slideGaps( self.newText, self.oldText );
            self.slideGaps( self.oldText, self.newText );
            if self.config.timer is True:
                self.timeEnd( 'character slide' );

        # Free memory
        self.symbols = Symbols(token=[], hashTable={}, linked=False);
        self.bordersDown.clear()
        self.bordersUp.clear()
        self.newText.words.clear()
        self.oldText.words.clear()

        # Enumerate token lists
        self.newText.enumerateTokens();
        self.oldText.enumerateTokens();

        # Detect moved blocks
        if self.config.timer is True:
            self.time( 'blocks' );
        self.detectBlocks();
        if self.config.timer is True:
            self.timeEnd( 'blocks' );

        # Free memory
        self.newText.tokens.clear()
        self.oldText.tokens.clear()

        # Assemble blocks into fragment table
        self.getDiffFragments();

        # Free memory
        self.blocks.clear()
        self.groups.clear()
        self.sections.clear()

        # Stop diff timer
        if self.config.timer is True:
            self.timeEnd( 'diff' );

        # Unit tests
        if self.config.unitTesting is True:
            # Test diff to test consistency between input and output
            if self.config.timer is True:
                self.time( 'unit tests' );
            self.unitTests();
            if self.config.timer is True:
                self.timeEnd( 'unit tests' );

        # Debug log
        if self.config.debug is True:
            self.debugFragments( 'Fragments before clipping' );

        # Clipping
        if self.config.fullDiff is False:
            # Clipping unchanged sections from unmoved block text
            if self.config.timer is True:
                self.time( 'clip' );
            self.clipDiffFragments();
            if self.config.timer is True:
                self.timeEnd( 'clip' );

        # Debug log
        if self.config.debug is True:
            self.debugFragments( 'Fragments' );

        # Create html formatted diff code from diff fragments
        if self.config.timer is True:
            self.time( 'html' );
        self.getDiffHtml();
        if self.config.timer is True:
            self.timeEnd( 'html' );

        # Free memory
        self.fragments.clear()

        # No change
        if self.html == '':
            self.html = self.config.htmlCode.containerStart + \
                        self.config.htmlCode.noChangeStart + \
                        self.htmlEscape( self.config.msg['wiked-diff-empty'] ) + \
                        self.config.htmlCode.noChangeEnd + \
                        self.config.htmlCode.containerEnd;

        # Add error indicator
        if self.error is True:
            self.html = self.config.htmlCode.errorStart + self.html + self.config.htmlCode.errorEnd;
            logger.error("The error flag is True")

        # Stop total timer
        if self.config.timer is True:
            self.timeEnd( 'total' );

        return self.html;


    ##
    ## Split tokens into chars in the following unresolved regions (gaps):
    ##   - One token became connected or separated by space or dash (or any token)
    ##   - Same number of tokens in gap and strong similarity of all tokens:
    ##     - Addition or deletion of flanking strings in tokens
    ##     - Addition or deletion of internal string in tokens
    ##     - Same length and at least 50 % identity
    ##     - Same start or end, same text longer than different text
    ## Identical tokens including space separators will be linked,
    ##   resulting in word-wise char-level diffs
    ##
    ## @param[in/out] WikEdDiffText newText, oldText Text object tokens list
    ##
    def splitRefineChars(self):

        # Find corresponding gaps.

        # Cycle through new text tokens list
        gaps = [];
        gap = None;
        i = self.newText.first;
        j = self.oldText.first;
        while i is not None:
            # Get token links
            newLink = self.newText.tokens[i].link;
            oldLink = None;
            if j is not None:
                oldLink = self.oldText.tokens[j].link;

            # Start of gap in new and old
            if gap is None and newLink is None and oldLink is None:
                gap = len(gaps)
                gaps.append( Gap(
                        newFirst  = i,
                        newLast   = i,
                        newTokens = 1,
                        oldFirst  = j,
                        oldLast   = j,
                        oldTokens = 0,
                        charSplit = None
                ) )

            # Count chars and tokens in gap
            elif gap is not None and newLink is None:
                gaps[gap].newLast = i;
                gaps[gap].newTokens += 1;

            # Gap ended
            elif gap is not None and newLink is not None:
                gap = None;

            # Next list elements
            if newLink is not None:
                j = self.oldText.tokens[newLink].next;
            i = self.newText.tokens[i].next;

        # Cycle through gaps and add old text gap data
        for gap in gaps:
            # Cycle through old text tokens list
            j = gap.oldFirst;
            while (
                    j is not None and
                    self.oldText.tokens[j] is not None and
                    self.oldText.tokens[j].link is None
                    ):
                # Count old chars and tokens in gap
                gap.oldLast = j;
                gap.oldTokens += 1;

                j = self.oldText.tokens[j].next;

        # Select gaps of identical token number and strong similarity of all tokens.
        for gap in gaps:
            charSplit = True;

            # Not same gap length
            if gap.newTokens != gap.oldTokens:
                # One word became separated by space, dash, or any string
                if gap.newTokens == 1 and gap.oldTokens == 3:
                    token = self.newText.tokens[ gap.newFirst ].token;
                    tokenFirst = self.oldText.tokens[ gap.oldFirst ].token;
                    tokenLast = self.oldText.tokens[ gap.oldLast ].token;
                    if (
                            token[ tokenFirst ] != 0 or
                            token[ tokenLast ] != len(token) - len(tokenLast)
                            ):
                        continue;
                elif gap.oldTokens == 1 and gap.newTokens == 3:
                    token = self.oldText.tokens[ gap.oldFirst ].token;
                    tokenFirst = self.newText.tokens[ gap.newFirst ].token;
                    tokenLast = self.newText.tokens[ gap.newLast ].token;
                    if not token.startswith(tokenFirst) or not token.endswith(tokenLast):
                        continue;
                else:
                    continue;
                gap.charSplit = True;

            # Cycle through new text tokens list and set charSplit
            else:
                i = gap.newFirst;
                j = gap.oldFirst;
                while i is not None:
                    newToken = self.newText.tokens[i].token;
                    oldToken = self.oldText.tokens[j].token;

                    # Get shorter and longer token
                    if len(newToken) < len(oldToken):
                        shorterToken = newToken;
                        longerToken = oldToken;
                    else:
                        shorterToken = oldToken;
                        longerToken = newToken;

                    # Not same token length
                    if len(newToken) != len(oldToken):

                        # Test for addition or deletion of internal string in tokens

                        # Find number of identical chars from left
                        left = 0;
                        while left < len(shorterToken):
                            if newToken[ left ] != oldToken[ left ]:
                                break;
                            left += 1;

                        # Find number of identical chars from right
                        right = 0;
                        while right < len(shorterToken):
                            if (
                                    newToken[ len(newToken) - 1 - right ] !=
                                    oldToken[ len(oldToken) - 1 - right ]
                                    ):
                                break;
                            right += 1;

                        # No simple insertion or deletion of internal string
                        if left + right != len(shorterToken):
                            # Not addition or deletion of flanking strings in tokens
                            # Smaller token not part of larger token
                            if shorterToken not in longerToken:
                                # Same text at start or end shorter than different text
                                if left < len(shorterToken) / 2 and right < len(shorterToken) / 2:
                                    # Do not split into chars in this gap
                                    charSplit = False;
                                    break;

                    # Same token length
                    elif newToken != oldToken:
                        # Tokens less than 50 % identical
                        ident = 0;
                        for pos in range(len(shorterToken)):
                            if shorterToken[ pos ] == longerToken[ pos ]:
                                ident += 1;
                        if ident / len(shorterToken) < 0.49:
                            # Do not split into chars this gap
                            charSplit = False;
                            break;

                    # Next list elements
                    if i == gap.newLast:
                        break;
                    i = self.newText.tokens[i].next;
                    j = self.oldText.tokens[j].next;
                gap.charSplit = charSplit;

        # Refine words into chars in selected gaps.
        for gap in gaps:
            if gap.charSplit is True:

                # Cycle through new text tokens list, link spaces, and split into chars
                i = gap.newFirst;
                j = gap.oldFirst;
                newGapLength = i - gap.newLast;
                oldGapLength = j - gap.oldLast;
                while i is not None or j is not None:

                    # Link identical tokens (spaces) to keep char refinement to words
                    if (
                            newGapLength == oldGapLength and
                            self.newText.tokens[i].token == self.oldText.tokens[j].token
                            ):
                        self.newText.tokens[i].link = j;
                        self.oldText.tokens[j].link = i;

                    # Refine words into chars
                    else:
                        if i is not None:
                            self.newText.splitText( 'character', i );
                        if j is not None:
                            self.oldText.splitText( 'character', j );

                    # Next list elements
                    if i == gap.newLast:
                        i = None;
                    if j == gap.oldLast:
                        j = None;
                    if i is not None:
                        i = self.newText.tokens[i].next;
                    if j is not None:
                        j = self.oldText.tokens[j].next;


    ##
    ## Move gaps with ambiguous identical fronts to last newline border or otherwise last word border.
    ##
    ## @param[in/out] wikEdDiffText text, textLinked These two are newText and oldText
    ##
    def slideGaps( self, text, textLinked ):

        regExpSlideBorder = self.config.regExp.slideBorder;
        regExpSlideStop = self.config.regExp.slideStop;

        # Cycle through tokens list
        i = text.first;
        gapStart = None;
        while i is not None:

            # Remember gap start
            if gapStart is None and text.tokens[i].link is None:
                gapStart = i;

            # Find gap end
            elif gapStart is not None and text.tokens[i].link is not None:
                gapFront = gapStart;
                gapBack = text.tokens[i].prev;

                # Slide down as deep as possible
                front = gapFront;
                back = text.tokens[gapBack].next;
                if (
                        front is not None and
                        back is not None and
                        text.tokens[front].link is None and
                        text.tokens[back].link is not None and
                        text.tokens[front].token == text.tokens[back].token
                        ):
                    text.tokens[front].link = text.tokens[back].link;
                    textLinked.tokens[ text.tokens[front].link ].link = front;
                    text.tokens[back].link = None

                    gapFront = text.tokens[gapFront].next;
                    gapBack = text.tokens[gapBack].next;

                    front = text.tokens[front].next;
                    back = text.tokens[back].next;

                # Test slide up, remember last line break or word border
                front = text.tokens[gapFront].prev;
                back = gapBack;
                gapFrontBlankTest = regExpSlideBorder.search( text.tokens[gapFront].token );
                frontStop = front;
                if text.tokens[back].link is None:
                    while (
                            front is not None and
                            back is not None and
                            text.tokens[front].link is not None and
                            text.tokens[front].token == text.tokens[back].token
                            ):
                        if front is not None:
                            # Stop at line break
                            if regExpSlideStop.search( text.tokens[front].token ) is True:
                                frontStop = front;
                                break;

# TODO: does this work? (comparison of re.match objects)
                            # Stop at first word border (blank/word or word/blank)
                            if regExpSlideBorder.search( text.tokens[front].token ) != gapFrontBlankTest:
                                frontStop = front;
                        front = text.tokens[front].prev;
                        back = text.tokens[back].prev;

                # Actually slide up to stop
                front = text.tokens[gapFront].prev;
                back = gapBack;
                while (
                        front is not None and
                        back is not None and
                        front != frontStop and
                        text.tokens[front].link is not None and
                        text.tokens[back].link is None and
                        text.tokens[front].token == text.tokens[back].token
                        ):
                    text.tokens[back].link = text.tokens[front].link;
                    textLinked.tokens[ text.tokens[back].link ].link = back;
                    text.tokens[front].link = None;

                    front = text.tokens[front].prev;
                    back = text.tokens[back].prev;
                gapStart = None;
            i = text.tokens[i].next;


    ##
    ## Calculate diff information, can be called repeatedly during refining.
    ## Links corresponding tokens from old and new text.
    ## Steps:
    ##   Pass 1: parse new text into symbol table
    ##   Pass 2: parse old text into symbol table
    ##   Pass 3: connect unique matching tokens
    ##   Pass 4: connect adjacent identical tokens downwards
    ##   Pass 5: connect adjacent identical tokens upwards
    ##   Repeat with empty symbol table (against crossed-over gaps)
    ##   Recursively diff still unresolved regions downwards with empty symbol table
    ##   Recursively diff still unresolved regions upwards with empty symbol table
    ##
    ## @param array symbols Symbol table object
    ## @param string level Split level: 'paragraph', 'line', 'sentence', 'chunk', 'word', 'character'
    ##
    ## Optionally for recursive or repeated calls:
    ## @param bool repeating Currently repeating with empty symbol table
    ## @param bool recurse Enable recursion
    ## @param int newStart, newEnd, oldStart, oldEnd Text object tokens indices
    ## @param int recursionLevel Recursion level
    ## @param[in/out] WikEdDiffText newText, oldText Text object, tokens list link property
    ##
    def calculateDiff(
                self,
                level,
                recurse=False,
                repeating=False,
                newStart=None,
                oldStart=None,
                up=False,
                recursionLevel=0
            ):

        # Set defaults
        if newStart is None:
            newStart=self.newText.first
        if oldStart is None:
            oldStart=self.oldText.first

        # Start timers
        if self.config.timer is True and repeating is False and recursionLevel == 0:
            self.time( level );
        if self.config.timer is True and repeating is False:
            self.time( level + str(recursionLevel) );

        # Get object symbols table and linked region borders
        if recursionLevel == 0 and repeating is False:
            symbols = self.symbols;
            bordersDown = self.bordersDown;
            bordersUp = self.bordersUp;

        # Create empty local symbols table and linked region borders arrays
        else:
            symbols = Symbols(token=[], hashTable={}, linked=False)
            bordersDown = [];
            bordersUp = [];

        # Updated versions of linked region borders
        bordersUpNext = [];
        bordersDownNext = [];

        ##
        ## Pass 1: parse new text into symbol table.
        ##

        # Cycle through new text tokens list
        i = newStart;
        while i is not None:
            if self.newText.tokens[i].link is None:
                # Add new entry to symbol table
                token = self.newText.tokens[i].token;
                if token not in symbols.hashTable:
                    symbols.hashTable[token] = len(symbols.token);
                    symbols.token.append( Symbol(
                            newCount=1,
                            oldCount=0,
                            newToken=i,
                            oldToken=None
                    ) );

                # Or update existing entry
                else:
                    # Increment token counter for new text
                    hashToArray = symbols.hashTable[token];
                    symbols.token[hashToArray].newCount += 1;

            # Stop after gap if recursing
            elif recursionLevel > 0:
                break;

            # Get next token
            if up is False:
                i = self.newText.tokens[i].next;
            else:
                i = self.newText.tokens[i].prev;

        ##
        ## Pass 2: parse old text into symbol table.
        ##

        # Cycle through old text tokens list
        j = oldStart;
        while j is not None:
            if self.oldText.tokens[j].link is None:
                # Add new entry to symbol table
                token = self.oldText.tokens[j].token;
                if token not in symbols.hashTable:
                    symbols.hashTable[token] = len(symbols.token)
                    symbols.token.append( Symbol(
                            newCount=0,
                            oldCount=1,
                            newToken=None,
                            oldToken=j
                    ) );

                # Or update existing entry
                else:
                    # Increment token counter for old text
                    hashToArray = symbols.hashTable[token];
                    symbols.token[hashToArray].oldCount += 1;

                    # Add token number for old text
                    symbols.token[hashToArray].oldToken = j;

            # Stop after gap if recursing
            elif recursionLevel > 0:
                break;

            # Get next token
            if up is False:
                j = self.oldText.tokens[j].next;
            else:
                j = self.oldText.tokens[j].prev;

        ##
        ## Pass 3: connect unique tokens.
        ##

        # Cycle through symbol array
        for symbolToken in symbols.token:
            # Find tokens in the symbol table that occur only once in both versions
            if symbolToken.newCount == 1 and symbolToken.oldCount == 1:
                newToken = symbolToken.newToken;
                oldToken = symbolToken.oldToken;
                newTokenObj = self.newText.tokens[newToken];
                oldTokenObj = self.oldText.tokens[oldToken];

                # Connect from new to old and from old to new
                if newTokenObj.link is None:
                    # Do not use spaces as unique markers
                    if self.config.regExp.blankOnlyToken.search( newTokenObj.token ):
                        # Link new and old tokens
                        newTokenObj.link = oldToken;
                        oldTokenObj.link = newToken;
                        symbols.linked = True;

                        # Save linked region borders
                        bordersDown.append( [newToken, oldToken] );
                        bordersUp.append( [newToken, oldToken] );

                        # Check if token contains unique word
                        if recursionLevel == 0:
                            unique = False;
                            if level == 'character':
                                unique = True;
                            else:
                                token = newTokenObj.token;
                                wordsGen = itertools.chain( self.config.regExp.countWords.finditer(token),
                                                            self.config.regExp.countChunks.finditer(token) )
                                words = [match.group() for match in wordsGen]

                                # Unique if longer than min block length
                                wordsLength = len(words)
                                if wordsLength >= self.config.blockMinLength:
                                    unique = True;

                                # Unique if it contains at least one unique word
                                else:
                                    for i in range(wordsLength):
                                        word = words[i];
# TODO how to replace Object. ... here?
#                                        if (
#                                                self.oldText.words[word] == 1 and
#                                                self.newText.words[word] == 1 and
#                                                Object.prototype.hasOwnProperty.call( self.oldText.words, word ) is True and
#                                                Object.prototype.hasOwnProperty.call( self.newText.words, word ) is True
#                                                ):
                                        if self.oldText.words[word] == 1 and self.newText.words[word] == 1:
                                            unique = True;
                                            break;

                            # Set unique
                            if unique is True:
                                newTokenObj.unique = True;
                                oldTokenObj.unique = True;

        # Continue passes only if unique tokens have been linked previously
        if symbols.linked is True:

            ##
            ## Pass 4: connect adjacent identical tokens downwards.
            ##

            # Cycle through list of linked new text tokens
            for border in bordersDown:
                i = border[0];
                j = border[1];

                # Next down
                iMatch = i;
                jMatch = j;
                i = self.newText.tokens[i].next;
                j = self.oldText.tokens[j].next;

                # Cycle through new text list gap region downwards
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None
                        ):

                    # Connect if same token
                    if self.newText.tokens[i].token == self.oldText.tokens[j].token:
                        self.newText.tokens[i].link = j;
                        self.oldText.tokens[j].link = i;

                    # Not a match yet, maybe in next refinement level
                    else:
                        bordersDownNext.append( [iMatch, jMatch] );
                        break;

                    # Next token down
                    iMatch = i;
                    jMatch = j;
                    i = self.newText.tokens[i].next;
                    j = self.oldText.tokens[j].next;

            ##
            ## Pass 5: connect adjacent identical tokens upwards.
            ##

            # Cycle through list of connected new text tokens
            for border in bordersUp:
                i = border[0];
                j = border[1];

                # Next up
                iMatch = i;
                jMatch = j;
                i = self.newText.tokens[i].prev;
                j = self.oldText.tokens[j].prev;

                # Cycle through new text gap region upwards
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None
                        ):

                    # Connect if same token
                    if self.newText.tokens[i].token == self.oldText.tokens[j].token:
                        self.newText.tokens[i].link = j;
                        self.oldText.tokens[j].link = i;

                    # Not a match yet, maybe in next refinement level
                    else:
                        bordersUpNext.append( [iMatch, jMatch] );
                        break;

                    # Next token up
                    iMatch = i;
                    jMatch = j;
                    i = self.newText.tokens[i].prev;
                    j = self.oldText.tokens[j].prev;

            ##
            ## Connect adjacent identical tokens downwards from text start.
            ## Treat boundary as connected, stop after first connected token.
            ##

            # Only for full text diff
            if recursionLevel == 0 and repeating is False:
                # From start
                i = self.newText.first;
                j = self.oldText.first;
                iMatch = None;
                jMatch = None;

                # Cycle through old text tokens down
                # Connect identical tokens, stop after first connected token
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None and
                        self.newText.tokens[i].token == self.oldText.tokens[j].token
                        ):
                    self.newText.tokens[i].link = j;
                    self.oldText.tokens[j].link = i;
                    iMatch = i;
                    jMatch = j;
                    i = self.newText.tokens[i].next;
                    j = self.oldText.tokens[j].next;
                if iMatch is not None:
                    bordersDownNext.append( [iMatch, jMatch] );

                # From end
                i = self.newText.last;
                j = self.oldText.last;
                iMatch = None;
                jMatch = None;

                # Cycle through old text tokens up
                # Connect identical tokens, stop after first connected token
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None and
                        self.newText.tokens[i].token == self.oldText.tokens[j].token
                        ):
                    self.newText.tokens[i].link = j;
                    self.oldText.tokens[j].link = i;
                    iMatch = i;
                    jMatch = j;
                    i = self.newText.tokens[i].prev;
                    j = self.oldText.tokens[j].prev;
                if iMatch is not None:
                    bordersUpNext.append( [iMatch, jMatch] );

            # Save updated linked region borders to object
            if recursionLevel == 0 and repeating is False:
                self.bordersDown = bordersDownNext;
                self.bordersUp = bordersUpNext;

            # Merge local updated linked region borders into object
            else:
                self.bordersDown += bordersDownNext
                self.bordersUp += bordersUpNext


            ##
            ## Repeat once with empty symbol table to link hidden unresolved common tokens in cross-overs.
            ## ("and" in "and this a and b that" -> "and this a and b that")
            ##

            if repeating is False and self.config.repeatedDiff is True:
                repeat = True;
                self.calculateDiff( level, recurse, repeat, newStart, oldStart, up, recursionLevel );

            ##
            ## Refine by recursively diffing not linked regions with new symbol table.
            ## At word and character level only.
            ## Helps against gaps caused by addition of common tokens around sequences of common tokens.
            ##

            if (
                    recurse is True and
                    self.config.recursiveDiff is True and
                    recursionLevel < self.config.recursionMax
                    ):
                ##
                ## Recursively diff gap downwards.
                ##

                # Cycle through list of linked region borders
                for border in bordersDownNext:
                    i = border[0];
                    j = border[1];

                    # Next token down
                    i = self.newText.tokens[i].next;
                    j = self.oldText.tokens[j].next;

                    # Start recursion at first gap token pair
                    if (
                            i is not None and
                            j is not None and
                            self.newText.tokens[i].link is None and
                            self.oldText.tokens[j].link is None
                            ):
                        repeat = False;
                        dirUp = False;
                        self.calculateDiff( level, recurse, repeat, i, j, dirUp, recursionLevel + 1 );

                ##
                ## Recursively diff gap upwards.
                ##

                # Cycle through list of linked region borders
                for border in bordersUpNext:
                    i = border[0];
                    j = border[1];

                    # Next token up
                    i = self.newText.tokens[i].prev;
                    j = self.oldText.tokens[j].prev;

                    # Start recursion at first gap token pair
                    if (
                            i is not None and
                            j is not None and
                            self.newText.tokens[i].link is None and
                            self.oldText.tokens[j].link is None
                            ):
                        repeat = False;
                        dirUp = True;
                        self.calculateDiff( level, recurse, repeat, i, j, dirUp, recursionLevel + 1 );

        # Stop timers
        if self.config.timer is True and repeating is False:
            self.recursionTimer.setdefault(recursionLevel, 0.0)
            self.recursionTimer[recursionLevel] += self.timeEnd( level + str(recursionLevel), True );
        if self.config.timer is True and repeating is False and recursionLevel == 0:
            self.timeRecursionEnd( level );
            self.timeEnd( level );


    ##
    ## Main method for processing raw diff data, extracting deleted, inserted, and moved blocks.
    ##
    ## Scheme of blocks, sections, and groups (old block numbers):
    ##   Old:      1    2 3D4   5E6    7   8 9 10  11
    ##             |    ‾/-/_    X     |    >|<     |
    ##   New:      1  I 3D4 2  E6 5  N 7  10 9  8  11
    ##   Section:       0 0 0   1 1       2 2  2
    ##   Group:    0 10 111 2  33 4 11 5   6 7  8   9
    ##   Fixed:    .    +++ -  ++ -    .   . -  -   +
    ##   Type:     =  . =-= =  -= =  . =   = =  =   =
    ##
    ## @param[out] array groups Groups table object
    ## @param[out] array blocks Blocks table object
    ## @param[in/out] WikEdDiffText newText, oldText Text object tokens list
    ##
    def detectBlocks(self):
        # Debug log
        if self.config.debug is True:
            self.oldText.debugText( 'Old text' );
            self.newText.debugText( 'New text' );

        # Collect identical corresponding ('=') blocks from old text and sort by new text
        self.getSameBlocks();

        # Collect independent block sections with no block move crosses outside a section
        self.getSections();

        # Find groups of continuous old text blocks
        self.getGroups();

        # Set longest sequence of increasing groups in sections as fixed (not moved)
        self.setFixed();

        # Convert groups to insertions/deletions if maximum block length is too short
        # Only for more complex texts that actually have blocks of minimum block length
        unlinkCount = 0;
        if (
                self.config.unlinkBlocks is True and
                self.config.blockMinLength > 0 and
                self.maxWords >= self.config.blockMinLength
                ):
            if self.config.timer is True:
                self.time( 'total unlinking' );

            # Repeat as long as unlinking is possible
            unlinked = True;
            while unlinked is True and unlinkCount < self.config.unlinkMax:
                # Convert '=' to '+'/'-' pairs
                unlinked = self.unlinkBlocks();

                # Start over after conversion
                if unlinked is True:
                    unlinkCount += 1;
                    self.slideGaps( self.newText, self.oldText );
                    self.slideGaps( self.oldText, self.newText );

                    # Repeat block detection from start
                    self.maxWords = 0;
                    self.getSameBlocks();
                    self.getSections();
                    self.getGroups();
                    self.setFixed();

            if self.config.timer is True:
                self.timeEnd( 'total unlinking' );

        # Collect deletion ('-') blocks from old text
        self.getDelBlocks();

        # Position '-' blocks into new text order
        self.positionDelBlocks();

        # Collect insertion ('+') blocks from new text
        self.getInsBlocks();

        # Set group numbers of '+' blocks
        self.setInsGroups();

        # Mark original positions of moved groups
        self.insertMarks();

        # Debug log
        if self.config.timer is True or self.config.debug is True:
            logger.debug( 'Unlink count: {}'.format(unlinkCount) );
        if self.config.debug is True:
            self.debugGroups( 'Groups' );
            self.debugBlocks( 'Blocks' );


    ##
    ## Collect identical corresponding matching ('=') blocks from old text and sort by new text.
    ##
    ## @param[in] WikEdDiffText newText, oldText Text objects
    ## @param[in/out] array blocks Blocks table object
    ##
    def getSameBlocks(self):

        if self.config.timer is True:
            self.time( 'getSameBlocks' );

        blocks = self.blocks;

        # Clear blocks array
        blocks.clear()

        # Cycle through old text to find connected (linked, matched) blocks
        j = self.oldText.first;
        i = None;
        while j is not None:
            # Skip '-' blocks
            while j is not None and self.oldText.tokens[j].link is None:
                j = self.oldText.tokens[j].next;

            # Get '=' block
            if j is not None:
                i = self.oldText.tokens[j].link;
                iStart = i;
                jStart = j;

                # Detect matching blocks ('=')
                count = 0;
                unique = False;
                text = '';
                while i is not None and j is not None and self.oldText.tokens[j].link == i:
                    text += self.oldText.tokens[j].token;
                    count += 1;
                    if self.newText.tokens[i].unique is True:
                        unique = True;
                    i = self.newText.tokens[i].next;
                    j = self.oldText.tokens[j].next;

                # Save old text '=' block
                blocks.append( Block(
                        oldBlock  = len(blocks),
                        newBlock  = None,
                        oldNumber = self.oldText.tokens[jStart].number,
                        newNumber = self.newText.tokens[iStart].number,
                        oldStart  = jStart,
                        count     = count,
                        unique    = unique,
                        words     = self.wordCount( text ),
                        chars     = len(text),
                        type      = '=',
                        section   = None,
                        group     = None,
                        fixed     = False,
                        moved     = None,
                        text      = text
                    ) )

        # Sort blocks by new text token number
        blocks.sort(key=lambda block: block.newNumber)

        # Number blocks in new text order
        for i, block in enumerate(blocks):
            block.newBlock = i;

        if self.config.timer is True:
            self.timeEnd( 'getSameBlocks' );


    ##
    ## Collect independent block sections with no block move crosses
    ## outside a section for per-section determination of non-moving fixed groups.
    ##
    ## @param[out] array sections Sections table object
    ## @param[in/out] array blocks Blocks table object, section property
    ##
    def getSections(self):

        if self.config.timer is True:
            self.time( 'getSections' );

        blocks = self.blocks;
        sections = self.sections;

        # Clear sections array
        sections.clear()

        # Cycle through blocks
        block = 0
        while block < len(blocks):
            sectionStart = block;
            sectionEnd = block;

            oldMax = blocks[sectionStart].oldNumber;
            sectionOldMax = oldMax;

            # Check right
            for j in range(sectionStart + 1, len(blocks)):
                # Check for crossing over to the left
                if blocks[j].oldNumber > oldMax:
                    oldMax = blocks[j].oldNumber;
                elif blocks[j].oldNumber < sectionOldMax:
                    sectionEnd = j;
                    sectionOldMax = oldMax;

            # Save crossing sections
            if sectionEnd > sectionStart:
                # Save section to block
                for i in range(sectionStart, sectionEnd + 1):
                    blocks[i].section = len(sections);

                # Save section
                sections.append( Section(
                        blockStart = sectionStart,
                        blockEnd   = sectionEnd
                    ) );
                block = sectionEnd;
                continue

            block += 1

        if self.config.timer is True:
            self.timeEnd( 'getSections' );


    ##
    ## Find groups of continuous old text blocks.
    ##
    ## @param[out] array groups Groups table object
    ## @param[in/out] array blocks Blocks table object, group property
    ##
    def getGroups(self):

        if self.config.timer is True:
            self.time( 'getGroups' );

        blocks = self.blocks;
        groups = self.groups;

        # Clear groups array
        groups.clear()

        # Cycle through blocks
        block = 0
        while block < len(blocks):
            groupStart = block;
            groupEnd = block;
            oldBlock = blocks[groupStart].oldBlock;

            # Get word and char count of block
            words = self.wordCount( blocks[block].text );
            maxWords = words;
            unique = blocks[block].unique;
            chars = blocks[block].chars;

            # Check right
            for i in range(groupEnd + 1, len(blocks)):
                # Check for crossing over to the left
                if blocks[i].oldBlock != oldBlock + 1:
                    break;
                oldBlock = blocks[i].oldBlock;

                # Get word and char count of block
                if blocks[i].words > maxWords:
                    maxWords = blocks[i].words;
                if blocks[i].unique is True:
                    unique = True;
                words += blocks[i].words;
                chars += blocks[i].chars;
                groupEnd = i;

            # Save crossing group
            if groupEnd >= groupStart:
                # Set groups outside sections as fixed
                fixed = False;
                if blocks[groupStart].section is None:
                    fixed = True;

                # Save group to block
                for i in range(groupStart, groupEnd + 1):
                    blocks[i].group = len(groups);
                    blocks[i].fixed = fixed;

                # Save group
                groups.append( Group(
                        oldNumber  = blocks[groupStart].oldNumber,
                        blockStart = groupStart,
                        blockEnd   = groupEnd,
                        unique     = unique,
                        maxWords   = maxWords,
                        words      = words,
                        chars      = chars,
                        fixed      = fixed,
                        movedFrom  = None,
                        color      = 0
                ) );
                block = groupEnd;

                # Set global word count of longest linked block
                if maxWords > self.maxWords:
                    self.maxWords = maxWords;

            block += 1

        if self.config.timer is True:
            self.timeEnd( 'getGroups' );


    ##
    ## Set longest sequence of increasing groups in sections as fixed (not moved).
    ##
    ## @param[in] array sections Sections table object
    ## @param[in/out] array groups Groups table object, fixed property
    ## @param[in/out] array blocks Blocks table object, fixed property
    ##
    def setFixed(self):

        if self.config.timer is True:
            self.time( 'setFixed' );

        blocks = self.blocks;
        groups = self.groups;
        sections = self.sections;

        # Cycle through sections
        for section in sections:
            blockStart = section.blockStart;
            blockEnd = section.blockEnd;

            groupStart = blocks[blockStart].group;
            groupEnd = blocks[blockEnd].group;

            # Recusively find path of groups in increasing old group order with longest char length
            cache = {};
            maxChars = 0;
            maxPath = None;

            # Start at each group of section
            for i in range(groupStart, groupEnd + 1):
                pathObj = self.findMaxPath( i, groupEnd, cache );
                if pathObj.chars > maxChars:
                    maxPath = pathObj.path;
                    maxChars = pathObj.chars;

            # Mark fixed groups
# TODO simplify
            for i in range(len(maxPath)):
                group = maxPath[i];
                groups[group].fixed = True;

                # Mark fixed blocks
                for block in range(groups[group].blockStart, groups[group].blockEnd + 1):
                    blocks[block].fixed = True;

        if self.config.timer is True:
            self.timeEnd( 'setFixed' );


    ##
    ## Recusively find path of groups in increasing old group order with longest char length.
    ##
    ## @param int start Path start group
    ## @param int groupEnd Path last group
    ## @param array cache Cache object, contains returnObj for start
    ## @return array returnObj Contains path and char length
    ##
    def findMaxPath( self, start, groupEnd, cache ):

        groups = self.groups;

        # Find longest sub-path
        maxChars = 0;
        oldNumber = groups[start].oldNumber;
        returnObj = CacheEntry( path=[], chars=0 )
        for i in range(start + 1, groupEnd + 1):
            # Only in increasing old group order
            if groups[i].oldNumber < oldNumber:
                continue;

            # Get longest sub-path from cache (deep copy)
            if i in cache:
# TODO deep vs. shallow
#                pathObj = CacheEntry( path=cache[i].path.slice(), chars=cache[i].chars )
                pathObj = CacheEntry( path=copy.deepcopy(cache[i].path), chars=cache[i].chars )
            # Get longest sub-path by recursion
            else:
                pathObj = self.findMaxPath( i, groupEnd, cache );

            # Select longest sub-path
            if pathObj.chars > maxChars:
                maxChars = pathObj.chars;
                returnObj = pathObj;

        # Add current start to path
        returnObj.path.insert( 0, start );
        returnObj.chars += groups[start].chars;

        # Save path to cache (deep copy)
        if start not in cache:
# TODO deep vs. shallow
#            cache.append( CacheEntry( path=returnObj.path.slice(), chars=returnObj.chars ) )
            cache[start] = CacheEntry( path=copy.deepcopy(returnObj.path), chars=returnObj.chars )

        return returnObj;


    ##
    ## Convert matching '=' blocks in groups into insertion/deletion ('+'/'-') pairs
    ## if too short and too common.
    ## Prevents fragmentated diffs for very different versions.
    ##
    ## @param[in] array blocks Blocks table object
    ## @param[in/out] WikEdDiffText newText, oldText Text object, linked property
    ## @param[in/out] array groups Groups table object
    ## @return bool True if text tokens were unlinked
    ##
    def unlinkBlocks(self):

        blocks = self.blocks;
        groups = self.groups;

        # Cycle through groups
        unlinked = False;
        for group in range(len(groups)):
            blockStart = groups[group].blockStart;
            blockEnd = groups[group].blockEnd;

            # Unlink whole group if no block is at least blockMinLength words long and unique
            if groups[group].maxWords < self.config.blockMinLength and groups[group].unique is False:
                for block in range(blockStart, blockEnd + 1):
                    if blocks[block].type == '=':
                        self.unlinkSingleBlock( blocks[block] );
                        unlinked = True;

            # Otherwise unlink block flanks
            else:
                # Unlink blocks from start
                for block in range(blockStart, blockEnd + 1):
                    if blocks[block].type == '=':
                        # Stop unlinking if more than one word or a unique word
                        if blocks[block].words > 1 or blocks[block].unique is True:
                            break;
                        self.unlinkSingleBlock( blocks[block] );
                        unlinked = True;
                        blockStart = block;

                # Unlink blocks from end
                for block in range(blockEnd, blockStart, -1):
                    if blocks[block].type == '=':
                        # Stop unlinking if more than one word or a unique word
                        if (
                                blocks[block].words > 1 or
                                ( blocks[block].words == 1 and blocks[block].unique is True )
                                ):
                            break;
                        self.unlinkSingleBlock( blocks[block] );
                        unlinked = True;

        return unlinked;


    ##
    ## Unlink text tokens of single block, convert them into into insertion/deletion ('+'/'-') pairs.
    ##
    ## @param[in] array blocks Blocks table object
    ## @param[out] WikEdDiffText newText, oldText Text objects, link property
    ##
    def unlinkSingleBlock( self, block ):

        # Cycle through old text
        j = block.oldStart;
        for count in range(block.count):
            # Unlink tokens
            self.newText.tokens[ self.oldText.tokens[j].link ].link = None
            self.oldText.tokens[j].link = None
            j = self.oldText.tokens[j].next;


    ##
    ## Collect deletion ('-') blocks from old text.
    ##
    ## @param[in] WikEdDiffText oldText Old Text object
    ## @param[out] array blocks Blocks table object
    ##
    def getDelBlocks(self):

        if self.config.timer is True:
            self.time( 'getDelBlocks' );

        blocks = self.blocks;

        # Cycle through old text to find connected (linked, matched) blocks
        j = self.oldText.first;
        i = None;
        while j is not None:
            # Collect '-' blocks
            oldStart = j;
            count = 0;
            text = '';
            while j is not None and self.oldText.tokens[j].link is None:
                count += 1;
                text += self.oldText.tokens[j].token;
                j = self.oldText.tokens[j].next;

            # Save old text '-' block
            if count != 0:
                blocks.append( Block(
                            oldBlock  = None,
                            newBlock  = None,
                            oldNumber = self.oldText.tokens[oldStart].number,
                            newNumber = None,
                            oldStart  = oldStart,
                            count     = count,
                            unique    = False,
                            words     = 0,
                            chars     = len(text),
                            type      = '-',
                            section   = None,
                            group     = None,
                            fixed     = False,
                            moved     = None,
                            text      = text
                    ) );

            # Skip '=' blocks
            if j is not None:
                i = self.oldText.tokens[j].link;
                while i is not None and j is not None and self.oldText.tokens[j].link == i:
                    i = self.newText.tokens[i].next;
                    j = self.oldText.tokens[j].next;

        if self.config.timer is True:
            self.timeEnd( 'getDelBlocks' );


    ##
    ## Position deletion '-' blocks into new text order.
    ## Deletion blocks move with fixed reference:
    ##   Old:          1 D 2      1 D 2
    ##                /     \    /   \ \
    ##   New:        1 D     2  1     D 2
    ##   Fixed:      *                  *
    ##   newNumber:  1 1              2 2
    ##
    ## Marks '|' and deletions '-' get newNumber of reference block
    ## and are sorted around it by old text number.
    ##
    ## @param[in/out] array blocks Blocks table, newNumber, section, group, and fixed properties
    ##
    ##
    def positionDelBlocks(self):

        if self.config.timer is True:
            self.time( 'positionDelBlocks' );

        blocks = self.blocks;
        groups = self.groups;

        # Sort shallow copy of blocks by oldNumber
        blocksOld = sorted(blocks, key=lambda block: block.oldNumber)

        # Cycle through blocks in old text order
        for block in range(len(blocksOld)):
            delBlock = blocksOld[block];

            # '-' block only
            if delBlock.type != '-':
                continue;

            # Find fixed '=' reference block from original block position to position '-' block
            # Similar to position marks '|' code

            # Get old text prev block
            prevBlockNumber = 0;
            prevBlock = 0;
            if block > 0:
                prevBlockNumber = blocksOld[block - 1].newBlock;
                prevBlock = blocks[prevBlockNumber];

            # Get old text next block
            nextBlockNumber = 0;
            nextBlock = 0;
            if block < len(blocksOld) - 1:
                nextBlockNumber = blocksOld[block + 1].newBlock;
                nextBlock = blocks[nextBlockNumber];

            # Move after prev block if fixed
            refBlock = 0;
            if prevBlock != 0 and prevBlock.type == '=' and prevBlock.fixed is True:
                refBlock = prevBlock;

            # Move before next block if fixed
            elif nextBlock != 0 and nextBlock.type == '=' and nextBlock.fixed is True:
                refBlock = nextBlock;

            # Move after prev block if not start of group
            elif (
                    prevBlock != 0 and
                    prevBlock.type == '=' and
                    prevBlockNumber != groups[ prevBlock.group ].blockEnd
                    ):
                refBlock = prevBlock;

            # Move before next block if not start of group
            elif (
                    nextBlock != 0 and
                    nextBlock.type == '=' and
                    nextBlockNumber != groups[ nextBlock.group ].blockStart
                    ):
                refBlock = nextBlock;

            # Move after closest previous fixed block
            else:
                for fixed in range(block, -1, -1):
                    if blocksOld[fixed].type == '=' and blocksOld[fixed].fixed is True:
                        refBlock = blocksOld[fixed];
                        break;

            # Move before first block
            if refBlock == 0:
                delBlock.newNumber =  -1;

            # Update '-' block data
            else:
                delBlock.newNumber = refBlock.newNumber;
                delBlock.section = refBlock.section;
                delBlock.group = refBlock.group;
                delBlock.fixed = refBlock.fixed;

        # Sort '-' blocks in and update groups
        self.sortBlocks();

        if self.config.timer is True:
            self.timeEnd( 'positionDelBlocks' );


    ##
    ## Collect insertion ('+') blocks from new text.
    ##
    ## @param[in] WikEdDiffText newText New Text object
    ## @param[out] array blocks Blocks table object
    ##
    def getInsBlocks(self):

        if self.config.timer is True:
            self.time( 'getInsBlocks' );

        blocks = self.blocks;

        # Cycle through new text to find insertion blocks
        i = self.newText.first;
        while i is not None:

            # Jump over linked (matched) block
            while i is not None and self.newText.tokens[i].link is not None:
                i = self.newText.tokens[i].next;

            # Detect insertion blocks ('+')
            if i is not None:
                iStart = i;
                count = 0;
                text = '';
                while i is not None and self.newText.tokens[i].link is None:
                    count += 1;
                    text += self.newText.tokens[i].token;
                    i = self.newText.tokens[i].next;

                # Save new text '+' block
                blocks.append( Block(
                        oldBlock  = None,
                        newBlock  = None,
                        oldNumber = None,
                        newNumber = self.newText.tokens[iStart].number,
                        oldStart  = None,
                        count     = count,
                        unique    = False,
                        words     = 0,
                        chars     = len(text),
                        type      = '+',
                        section   = None,
                        group     = None,
                        fixed     = False,
                        moved     = None,
                        text      = text
                ) );

        # Sort '+' blocks in and update groups
        self.sortBlocks();

        if self.config.timer is True:
            self.timeEnd( 'getInsBlocks' );


    ##
    ## Sort blocks by new text token number and update groups.
    ##
    ## @param[in/out] array groups Groups table object
    ## @param[in/out] array blocks Blocks table object
    ##
    def sortBlocks(self):

        blocks = self.blocks;
        groups = self.groups;

        # Sort by newNumber, then by old number
        blocks.sort(key=lambda block: (int_or_null(block.newNumber), int_or_null(block.oldNumber)))

        # Cycle through blocks and update groups with new block numbers
        group = 0
        for block in range(len(blocks)):
            blockGroup = blocks[block].group;
            if blockGroup is not None and blockGroup < len(groups):
                if blockGroup != group:
                    group = blocks[block].group;
                    groups[group].blockStart = block;
                    groups[group].oldNumber = blocks[block].oldNumber;
                groups[blockGroup].blockEnd = block;


    ##
    ## Set group numbers of insertion '+' blocks.
    ##
    ## @param[in/out] array groups Groups table object
    ## @param[in/out] array blocks Blocks table object, fixed and group properties
    ##
    def setInsGroups(self):

        if self.config.timer is True:
            self.time( 'setInsGroups' );

        blocks = self.blocks;
        groups = self.groups;

        # Set group numbers of '+' blocks inside existing groups
        for group in range(len(groups)):
            fixed = groups[group].fixed;
            for block in range(groups[group].blockStart, groups[group].blockEnd + 1):
                if blocks[block].group is None:
                    blocks[block].group = group;
                    blocks[block].fixed = fixed;

        # Add remaining '+' blocks to new groups

        # Cycle through blocks
        for block in range(len(blocks)):
            # Skip existing groups
            if blocks[block].group is None:
                blocks[block].group = len(groups);

                # Save new single-block group
                groups.append( Group(
                        oldNumber  = blocks[block].oldNumber,
                        blockStart = block,
                        blockEnd   = block,
                        unique     = blocks[block].unique,
                        maxWords   = blocks[block].words,
                        words      = blocks[block].words,
                        chars      = blocks[block].chars,
                        fixed      = blocks[block].fixed,
                        movedFrom  = None,
                        color      = 0
                ) );

        if self.config.timer is True:
            self.timeEnd( 'setInsGroups' );


    ##
    ## Mark original positions of moved groups.
    ## Scheme: moved block marks at original positions relative to fixed groups:
    ##   Groups:    3       7
    ##           1 <|       |     (no next smaller fixed)
    ##           5  |<      |
    ##              |>  5   |
    ##              |   5  <|
    ##              |      >|   5
    ##              |       |>  9 (no next larger fixed)
    ##   Fixed:     *       *
    ##
    ## Mark direction: groups.movedGroup.blockStart < groups.group.blockStart
    ## Group side:     groups.movedGroup.oldNumber < groups.group.oldNumber
    ##
    ## Marks '|' and deletions '-' get newNumber of reference block
    ## and are sorted around it by old text number.
    ##
    ## @param[in/out] array groups Groups table object, movedFrom property
    ## @param[in/out] array blocks Blocks table object
    ##
    def insertMarks(self):

        if self.config.timer is True:
            self.time( 'insertMarks' );

        blocks = self.blocks;
        groups = self.groups;
        moved = [];
        color = 1;

        # Make shallow copy of blocks
        blocksOld = blocks[:]

        # Enumerate copy
        for i, block in enumerate(blocksOld):
            block.number = i;

        # Sort copy by oldNumber, then by newNumber
        blocksOld.sort(key=lambda block: (int_or_null(block.oldNumber), int_or_null(block.newNumber)))

        # Create lookup table: original to sorted
        lookupSorted = {};
        for i in range(len(blocksOld)):
            lookupSorted[ blocksOld[i].number ] = i;

        # Cycle through groups (moved group)
        for moved in range(len(groups)):
            movedGroup = groups[moved];
            # NOTE: In JavaScript original there were 3 possible values for .fixed:
            #       true, false and null and only .fixed==false entries were processed
            #       in this loop. I think that the fixed==null entries correspond to
            #       those with .oldNumber==None.
            if movedGroup.fixed is True or movedGroup.oldNumber is None:
                continue;
            movedOldNumber = movedGroup.oldNumber;

            # Find fixed '=' reference block from original block position to position '|' block
            # Similar to position deletions '-' code

            # Get old text prev block
            prevBlock = None;
            block = lookupSorted[ movedGroup.blockStart ];
            if block > 0:
                prevBlock = blocksOld[block - 1];

            # Get old text next block
            nextBlock = None;
            block = lookupSorted[ movedGroup.blockEnd ];
            if block < len(blocksOld) - 1:
                nextBlock = blocksOld[block + 1];

            # Move after prev block if fixed
            refBlock = None;
            if prevBlock is not None and prevBlock.type == '=' and prevBlock.fixed is True:
                refBlock = prevBlock;

            # Move before next block if fixed
            elif nextBlock is not None and nextBlock.type == '=' and nextBlock.fixed is True:
                refBlock = nextBlock;

            # Find closest fixed block to the left
            else:
                for fixed in range(lookupSorted[ movedGroup.blockStart ] - 1, -1, -1):
                    if blocksOld[fixed].type == '=' and blocksOld[fixed].fixed is True:
                        refBlock = blocksOld[fixed];
                        break;

            # Get position of new mark block

            # No smaller fixed block, moved right from before first block
            if refBlock is None:
                newNumber = -1;
                markGroup = len(groups);

                # Save new single-mark-block group
                groups.append( Group(
                        oldNumber  = None,
                        blockStart = len(blocks),
                        blockEnd   = len(blocks),
                        unique     = False,
                        maxWords   = None,
                        words      = 0,
                        chars      = 0,
                        fixed      = False,
                        movedFrom  = None,
                        color      = 0
                ) );
            else:
                newNumber = refBlock.newNumber;
                markGroup = refBlock.group;

            # Insert '|' block
            blocks.append( Block(
                    oldBlock  = None,
                    newBlock  = None,
                    oldNumber = movedOldNumber,
                    newNumber = newNumber,
                    oldStart  = None,
                    count     = None,
                    unique    = None,
                    words     = 0,
                    chars     = 0,
                    type      = '|',
                    section   = None,
                    group     = markGroup,
                    fixed     = True,
                    moved     = moved,
                    text      = ''
            ) );

            # Set group color
            movedGroup.color = color;
            movedGroup.movedFrom = markGroup;
            color += 1;

        # Sort '|' blocks in and update groups
        self.sortBlocks();

        if self.config.timer is True:
            self.timeEnd( 'insertMarks' );


    ##
    ## Collect diff fragment list for markup, create abstraction layer for customized diffs.
    ## Adds the following fagment types:
    ##   '=', '-', '+'   same, deletion, insertion
    ##   '<', '>'        mark left, mark right
    ##   '(<', '(>', ')' block start and end
    ##   '[', ']'        fragment start and end
    ##   '{', '}'        container start and end
    ##
    ## @param[in] array groups Groups table object
    ## @param[in] array blocks Blocks table object
    ## @param[out] array fragments Fragments array, abstraction layer for diff code
    ##
    def getDiffFragments(self):

        blocks = self.blocks;
        groups = self.groups;
        fragments = self.fragments;

        # Make shallow copy of groups and sort by blockStart
        groupsSort = sorted(groups, key=lambda group: group.blockStart)

        # Cycle through groups
        for group in range(len(groupsSort)):
            blockStart = groupsSort[group].blockStart;
            blockEnd = groupsSort[group].blockEnd;

            # Add moved block start
            color = groupsSort[group].color;
            if color != 0:
                if groupsSort[group].movedFrom < blocks[ blockStart ].group:
                    type = '(<';
                else:
                    type = '(>';
                fragments.append( Fragment(
                        text  = '',
                        type  = type,
                        color = color
                ) );

            # Cycle through blocks
            for block in range(blockStart, blockEnd + 1):
                type = blocks[block].type;

                # Add '=' unchanged text and moved block
                if type == '=' or type == '-' or type == '+':
                    fragments.append( Fragment(
                            text  = blocks[block].text,
                            type  = type,
                            color = color
                    ) );

                # Add '<' and '>' marks
                elif type == '|':
                    movedGroup = groups[ blocks[block].moved ];

                    # Get mark text
                    markText = '';
                    for movedBlock in range(movedGroup.blockStart, movedGroup.blockEnd + 1):
                        if blocks[movedBlock].type == '=' or blocks[movedBlock].type == '-':
                            markText += blocks[movedBlock].text;

                    # Get mark direction
                    if movedGroup.blockStart < blockStart:
                        markType = '<';
                    else:
                        markType = '>';

                    # Add mark
                    fragments.append( Fragment(
                            text  = markText,
                            type  = markType,
                            color = movedGroup.color
                    ) );

            # Add moved block end
            if color != 0:
                fragments.append( Fragment(
                        text  = '',
                        type  = ' )',
                        color = color
                ) );

        # Cycle through fragments, join consecutive fragments of same type (i.e. '-' blocks)
        fragment = 1
        while fragment < len(fragments):
            # Check if joinable
            if (
                    fragments[fragment].type == fragments[fragment - 1].type and
                    fragments[fragment].color == fragments[fragment - 1].color and
                    fragments[fragment].text != '' and fragments[fragment - 1].text != ''
                    ):
                # Join and splice
                fragments[fragment - 1].text += fragments[fragment].text;
                fragments.pop(fragment)
                fragment -= 1;
            fragment += 1

        # Enclose in containers
        fragments.insert( 0, Fragment( text='', type='{', color=0 ) )
        fragments.insert( 1, Fragment( text='', type='[', color=0 ) )
        fragments.append(    Fragment( text='', type=']', color=0 ) )
        fragments.append(    Fragment( text='', type='}', color=0 ) )


    ##
    ## Clip unchanged sections from unmoved block text.
    ## Adds the following fagment types:
    ##   '~', ' ~', '~ ' omission indicators
    ##   '[', ']', ','   fragment start and end, fragment separator
    ##
    ## @param[in/out] array fragments Fragments array, abstraction layer for diff code
    ##
    def clipDiffFragments(self):

        fragments = self.fragments;

        # Skip if only one fragment in containers, no change
        if len(fragments) == 5:
            return;

        # Min length for clipping right
        minRight = self.config.clipHeadingRight;
        if self.config.clipParagraphRightMin < minRight:
            minRight = self.config.clipParagraphRightMin;
        if self.config.clipLineRightMin < minRight:
            minRight = self.config.clipLineRightMin;
        if self.config.clipBlankRightMin < minRight:
            minRight = self.config.clipBlankRightMin;
        if self.config.clipCharsRight < minRight:
            minRight = self.config.clipCharsRight;

        # Min length for clipping left
        minLeft = self.config.clipHeadingLeft;
        if self.config.clipParagraphLeftMin < minLeft:
            minLeft = self.config.clipParagraphLeftMin;
        if self.config.clipLineLeftMin < minLeft:
            minLeft = self.config.clipLineLeftMin;
        if self.config.clipBlankLeftMin < minLeft:
            minLeft = self.config.clipBlankLeftMin;
        if self.config.clipCharsLeft < minLeft:
            minLeft = self.config.clipCharsLeft;

        # Cycle through fragments
        fragment = -1
        while fragment + 1 < len(fragments):
            fragment += 1

            # Skip if not an unmoved and unchanged block
            type = fragments[fragment].type;
            color = fragments[fragment].color;
            if type != '=' or color != 0:
                continue;

            # Skip if too short for clipping
            text = fragments[fragment].text;
            if len(text) < minRight and len(text) < minLeft:
                continue;

            # Get line positions including start and end
            lines = [];
            lastIndex = 0;
            for regExpMatch in self.config.regExp.clipLine.finditer(text):
                lines.append( regExpMatch.start() );
                lastIndex = regExpMatch.end()
            if lines[0] != 0:
                lines.insert( 0, 0 );
            if lastIndex != len(text):
                lines.append(len(text));

            # Get heading positions
            headings = [];
            headingsEnd = [];
            for regExpMatch in self.config.regExp.clipHeading.finditer(text):
                headings.append( regExpMatch.start() )
                headingsEnd.append( regExpMatch.end() )

            # Get paragraph positions including start and end
            paragraphs = [];
            lastIndex = 0
            for regExpMatch in self.config.regExp.clipParagraph.finditer(text):
                paragraphs.append( regExpMatch.start() );
                lastIndex = regExpMatch.end()
            if len(paragraphs) == 0 or paragraphs[0] != 0:
                paragraphs.insert( 0, 0 );
            if lastIndex != len(text):
                paragraphs.append( len(text) );

            # Determine ranges to keep on left and right side
            rangeRight = None;
            rangeLeft = None;
            rangeRightType = '';
            rangeLeftType = '';

            # Find clip pos from left, skip for first non-container block
            if fragment != 2:
                # Maximum lines to search from left
                rangeLeftMax = len(text);
                if self.config.clipLinesLeftMax < len(lines):
                    rangeLeftMax = lines[self.config.clipLinesLeftMax];

                # Find first heading from left
                if rangeLeft is None:
                    for j in range(len(headingsEnd)):
                        if headingsEnd[j] > self.config.clipHeadingLeft or headingsEnd[j] > rangeLeftMax:
                            break;
                        rangeLeft = headingsEnd[j];
                        rangeLeftType = 'heading';
                        break;

                # Find first paragraph from left
                if rangeLeft is None:
                    for j in range(len(paragraphs)):
                        if (
                                paragraphs[j] > self.config.clipParagraphLeftMax or
                                paragraphs[j] > rangeLeftMax
                                ):
                            break;
                        if paragraphs[j] > self.config.clipParagraphLeftMin:
                            rangeLeft = paragraphs[j];
                            rangeLeftType = 'paragraph';
                            break;

                # Find first line break from left
                if rangeLeft is None:
                    for j in range(len(lines)):
                        if lines[j] > self.config.clipLineLeftMax or lines[j] > rangeLeftMax:
                            break;
                        if lines[j] > self.config.clipLineLeftMin:
                            rangeLeft = lines[j];
                            rangeLeftType = 'line';
                            break;

                # Find first blank from left
                if rangeLeft is None:
                    regExpMatch = self.config.regExp.clipBlank.search(text, pos=self.config.clipBlankLeftMin)
                    if regExpMatch:
                        if (
                                regExpMatch.start() < self.config.clipBlankLeftMax and
                                regExpMatch.start() < rangeLeftMax
                                ):
                            rangeLeft = regExpMatch.start();
                            rangeLeftType = 'blank';

                # Fixed number of chars from left
                if rangeLeft is None:
                    if self.config.clipCharsLeft < rangeLeftMax:
                        rangeLeft = self.config.clipCharsLeft;
                        rangeLeftType = 'chars';

                # Fixed number of lines from left
                if rangeLeft is None:
                    rangeLeft = rangeLeftMax;
                    rangeLeftType = 'fixed';

            # Find clip pos from right, skip for last non-container block
            if fragment != len(fragments) - 3:
                # Maximum lines to search from right
                rangeRightMin = 0;
                if len(lines) >= self.config.clipLinesRightMax:
                    rangeRightMin = lines[len(lines) - self.config.clipLinesRightMax];

                # Find last heading from right
                if rangeRight is None:
                    for j in range(len(headings) - 1, -1, -1):
                        if (
                                headings[j] < len(text) - self.config.clipHeadingRight or
                                headings[j] < rangeRightMin
                                ):
                            break;
                        rangeRight = headings[j];
                        rangeRightType = 'heading';
                        break;

                # Find last paragraph from right
                if rangeRight is None:
                    for j in range(len(paragraphs) - 1, -1, -1):
                        if (
                                paragraphs[j] < len(text) - self.config.clipParagraphRightMax or
                                paragraphs[j] < rangeRightMin
                                ):
                            break;
                        if paragraphs[j] < len(text) - self.config.clipParagraphRightMin:
                            rangeRight = paragraphs[j];
                            rangeRightType = 'paragraph';
                            break;

                # Find last line break from right
                if rangeRight is None:
                    for j in range(len(lines) - 1, -1, -1):
                        if (
                                lines[j] < len(text) - self.config.clipLineRightMax or
                                lines[j] < rangeRightMin
                                ):
                            break;
                        if lines[j] < len(text) - self.config.clipLineRightMin:
                            rangeRight = lines[j];
                            rangeRightType = 'line';
                            break;

                # Find last blank from right
                if rangeRight is None:
                    startPos = len(text) - self.config.clipBlankRightMax;
                    if startPos < rangeRightMin:
                        startPos = rangeRightMin;
                    lastPos = None;
                    regExpMatches = self.config.regExp.clipBlank.finditer(text, pos=startPos)
                    for regExpMatch in regExpMatches:
                        if regExpMatch.start() > len(text) - self.config.clipBlankRightMin:
                            if lastPos is not None:
                                rangeRight = lastPos;
                                rangeRightType = 'blank';
                            break;
                        lastPos = regExpMatch.start()

                # Fixed number of chars from right
                if rangeRight is None:
                    if len(text) - self.config.clipCharsRight > rangeRightMin:
                        rangeRight = len(text) - self.config.clipCharsRight;
                        rangeRightType = 'chars';

                # Fixed number of lines from right
                if rangeRight is None:
                    rangeRight = rangeRightMin;
                    rangeRightType = 'fixed';

            # Check if we skip clipping if ranges are close together
            if rangeLeft is not None and rangeRight is not None:
                # Skip if overlapping ranges
                if rangeLeft > rangeRight:
                    continue;

                # Skip if chars too close
                skipChars = rangeRight - rangeLeft;
                if skipChars < self.config.clipSkipChars:
                    continue;

                # Skip if lines too close
                skipLines = 0;
                for j in range(len(lines)):
                    if lines[j] > rangeRight or skipLines > self.config.clipSkipLines:
                        break;
                    if lines[j] > rangeLeft:
                        skipLines += 1;
                if skipLines < self.config.clipSkipLines:
                    continue;

            # Skip if nothing to clip
            if rangeLeft is None and rangeRight is None:
                continue;

            # Split left text
            textLeft = None;
            omittedLeft = None;
            if rangeLeft is not None:
                textLeft = text[ :rangeLeft ]

                # Remove trailing empty lines
                textLeft = self.config.regExp.clipTrimNewLinesLeft.sub( "", textLeft )

                # Get omission indicators, remove trailing blanks
                if rangeLeftType == 'chars':
                    omittedLeft = '~';
                    textLeft = self.config.regExp.clipTrimBlanksLeft.sub( "", textLeft )
                elif rangeLeftType == 'blank':
                    omittedLeft = ' ~';
                    textLeft = self.config.regExp.clipTrimBlanksLeft.sub( "", textLeft )

            # Split right text
            textRight = None;
            omittedRight = None;
            if rangeRight is not None:
                textRight = text[ rangeRight: ]

                # Remove leading empty lines
                textRight = self.config.regExp.clipTrimNewLinesRight.sub( "", textRight )

                # Get omission indicators, remove leading blanks
                if rangeRightType == 'chars':
                    omittedRight = '~';
                    textRight = self.config.regExp.clipTrimBlanksRight.sub( "", textRight )
                elif rangeRightType == 'blank':
                    omittedRight = '~ ';
                    textRight = self.config.regExp.clipTrimBlanksRight.sub( "", textRight )

            # Remove split element
            fragments.pop( fragment )

            # Add left text to fragments list
            if rangeLeft is not None:
                fragments.insert( fragment, Fragment( text=textLeft, type='=', color=0 ) );
                fragment += 1
                if omittedLeft is not None:
                    fragments.insert( fragment, Fragment( text='', type=omittedLeft, color=0 ) );
                    fragment += 1

            # Add fragment container and separator to list
            if rangeLeft is not None and rangeRight is not None:
                fragments.insert( fragment, Fragment( text='', type=']', color=0 ) );
                fragment += 1
                fragments.insert( fragment, Fragment( text='', type=',', color=0 ) );
                fragment += 1
                fragments.insert( fragment, Fragment( text='', type='[', color=0 ) );
                fragment += 1

            # Add right text to fragments list
            if rangeRight is not None:
                if omittedRight is not None:
                    fragments.insert( fragment, Fragment( text='', type=omittedRight, color=0 ) );
                    fragment += 1
                fragments.insert( fragment, Fragment( text=textRight, type='=', color=0 ) );
                fragment += 1


    ##
    ## Create html formatted diff code from diff fragments.
    ##
    ## @param[in] array fragments Fragments array, abstraction layer for diff code
    ## @param string|undefined version
    ##   Output version: 'new' or 'old': only text from new or old version, used for unit tests
    ## @param[out] string html Html code of diff
    ##
    def getDiffHtml( self, version=None ):

        fragments = self.fragments;

        # No change, only one unchanged block in containers
        if len(fragments) == 5 and fragments[2].type == '=':
            self.html = '';
            return;

        # Cycle through fragments
        htmlFragments = [];
        for fragment in fragments:
            text = fragment.text;
            type = fragment.type;
            color = fragment.color;
            html = '';

            # Test if text is blanks-only or a single character
            blank = False;
            if text != '':
                blank = self.config.regExp.blankBlock.search( text );

            # Add container start markup
            if type == '{':
                html = self.config.htmlCode.containerStart;
            # Add container end markup
            elif type == '}':
                html = self.config.htmlCode.containerEnd;

            # Add fragment start markup
            if type == '[':
                html = self.config.htmlCode.fragmentStart;
            # Add fragment end markup
            elif type == ']':
                html = self.config.htmlCode.fragmentEnd;
            # Add fragment separator markup
            elif type == ',':
                html = self.config.htmlCode.separator;

            # Add omission markup
            if type == '~':
                html = self.config.htmlCode.omittedChars;

            # Add omission markup
            if type == ' ~':
                html = ' ' + self.config.htmlCode.omittedChars;

            # Add omission markup
            if type == '~ ':
                html = self.config.htmlCode.omittedChars + ' ';
            # Add colored left-pointing block start markup
            elif type == '(<':
                if version != 'old':
                    # Get title
                    if self.config.noUnicodeSymbols is True:
                        title = self.config.msg['wiked-diff-block-left-nounicode'];
                    else:
                        title = self.config.msg['wiked-diff-block-left'];

                    # Get html
                    if self.config.coloredBlocks is True:
                        html = self.config.htmlCode.blockColoredStart;
                    else:
                        html = self.config.htmlCode.blockStart;
                    html = self.htmlCustomize( html, color, title );

            # Add colored right-pointing block start markup
            elif type == '(>':
                if version != 'old':
                    # Get title
                    if self.config.noUnicodeSymbols is True:
                        title = self.config.msg['wiked-diff-block-right-nounicode'];
                    else:
                        title = self.config.msg['wiked-diff-block-right'];

                    # Get html
                    if self.config.coloredBlocks is True:
                        html = self.config.htmlCode.blockColoredStart;
                    else:
                        html = self.config.htmlCode.blockStart;
                    html = self.htmlCustomize( html, color, title );

            # Add colored block end markup
            elif type == ' )':
                if version != 'old':
                    html = self.config.htmlCode.blockEnd;

            # Add '=' (unchanged) text and moved block
            if type == '=':
                text = self.htmlEscape( text );
                if color != 0:
                    if version != 'old':
                        html = self.markupBlanks( text, True );
                else:
                    html = self.markupBlanks( text );

            # Add '-' text
            elif type == '-':
                if version != 'new':
                    # For old version skip '-' inside moved group
                    if version != 'old' or color == 0:
                        text = self.htmlEscape( text );
                        text = self.markupBlanks( text, True );
                        if blank is True:
                            html = self.config.htmlCode.deleteStartBlank;
                        else:
                            html = self.config.htmlCode.deleteStart;
                        html += text + self.config.htmlCode.deleteEnd;

            # Add '+' text
            elif type == '+':
                if version != 'old':
                    text = self.htmlEscape( text );
                    text = self.markupBlanks( text, True );
                    if blank is True:
                        html = self.config.htmlCode.insertStartBlank;
                    else:
                        html = self.config.htmlCode.insertStart;
                    html += text + self.config.htmlCode.insertEnd;

            # Add '<' and '>' code
            elif type == '<' or type == '>':
                if version != 'new':
                    # Display as deletion at original position
                    if self.config.showBlockMoves is False or version == 'old':
                        text = self.htmlEscape( text );
                        text = self.markupBlanks( text, True );
                        if version == 'old':
                            if self.config.coloredBlocks is True:
                                html = self.htmlCustomize( self.config.htmlCode.blockColoredStart, color ) + \
                                       text + \
                                       self.config.htmlCode.blockEnd;
                            else:
                                html = self.htmlCustomize( self.config.htmlCode.blockStart, color ) + \
                                       text + \
                                       self.config.htmlCode.blockEnd;
                        else:
                            if blank is True:
                                html = self.config.htmlCode.deleteStartBlank + \
                                       text + \
                                       self.config.htmlCode.deleteEnd;
                            else:
                                html = self.config.htmlCode.deleteStart + text + self.config.htmlCode.deleteEnd;

                    # Display as mark
                    else:
                        if type == '<':
                            if self.config.coloredBlocks is True:
                                html = self.htmlCustomize( self.config.htmlCode.markLeftColored, color, text );
                            else:
                                html = self.htmlCustomize( self.config.htmlCode.markLeft, color, text );
                        else:
                            if self.config.coloredBlocks is True:
                                html = self.htmlCustomize( self.config.htmlCode.markRightColored, color, text );
                            else:
                                html = self.htmlCustomize( self.config.htmlCode.markRight, color, text );

            htmlFragments.append( html );

        # Join fragments
        self.html = "".join(htmlFragments)


    ##
    ## Customize html code fragments.
    ## Replaces:
    ##   {number}:    class/color/block/mark/id number
    ##   {title}:     title attribute (popup)
    ##   {nounicode}: noUnicodeSymbols fallback
    ##   input: html, number: block number, title: title attribute (popup) text
    ##
    ## @param string html Html code to be customized
    ## @return string Customized html code
    ##
    def htmlCustomize( self, html, number, title=None ):

        # Replace {number} with class/color/block/mark/id number
        html = html.replace("{number}", str(number));

        # Replace {nounicode} with wikEdDiffNoUnicode class name
        if self.config.noUnicodeSymbols is True:
            html = html.replace("{nounicode}", ' wikEdDiffNoUnicode');
        else:
            html = html.replace("{nounicode}", '');

        # Shorten title text, replace {title}
        if title != None:
            max = 512;
            end = 128;
            gapMark = ' [...] ';
            if len(title) > max:
                title = title[ : max - len(gapMark) - end ] + \
                        gapMark + \
                        title[ len(title) - end : ];
            title = self.htmlEscape( title );
            title = title.replace("\t", '&nbsp;&nbsp;');
            title = title.replace("  ", '&nbsp;&nbsp;');
            html = html.replace("{title}", title);

        return html;


    ##
    ## Replace html-sensitive characters in output text with character entities.
    ##
    ## @param string html Html code to be escaped
    ## @return string Escaped html code
    ##
    def htmlEscape( self, html ):

        html = html.replace("&", '&amp;');
        html = html.replace("<", '&lt;');
        html = html.replace(">", '&gt;');
        html = html.replace('"', '&quot;');
        return html;


    ##
    ## Markup tabs, newlines, and spaces in diff fragment text.
    ##
    ## @param bool highlight Highlight newlines and spaces in addition to tabs
    ## @param string html Text code to be marked-up
    ## @return string Marked-up text
    ##
    def markupBlanks( self, html, highlight=False ):

        if highlight is True:
            html = html.replace(" ", self.config.htmlCode.space);
            html = html.replace("\n", self.config.htmlCode.newline);
        html = html.replace("\t", self.config.htmlCode.tab);
        return html;


    ##
    ## Count real words in text.
    ##
    ## @param string text Text for word counting
    ## @return int Number of words in text
    ##
    def wordCount( self, text ):

        return len(self.config.regExp.countWords.findall(text))


    ##
    ## Test diff code for consistency with input versions.
    ## Prints results to debug console.
    ##
    ## @param[in] WikEdDiffText newText, oldText Text objects
    ##
    def unitTests(self):

        # Check if output is consistent with new text
        self.getDiffHtml( 'new' )
        diff = re.sub("<[^>]*>", "", self.html)
        text = self.htmlEscape( self.newText.text )
        if diff != text:
            logger.debug(
                    'Error: wikEdDiff unit test failure: diff not consistent with new text version!'
            );
            self.error = True;
            logger.debug( 'new text:\n' + text );
            logger.debug( 'new diff:\n' + diff );
        else:
            logger.debug( 'OK: wikEdDiff unit test passed: diff consistent with new text.' );

        # Check if output is consistent with old text
        self.getDiffHtml( 'old' )
        diff = re.sub("<[^>]*>", "", self.html)
        text = self.htmlEscape( self.oldText.text )
        if diff != text:
            logger.debug(
                    'Error: wikEdDiff unit test failure: diff not consistent with old text version!'
            );
            self.error = True;
            logger.debug( 'old text:\n' + text );
            logger.debug( 'old diff:\n' + diff );
        else:
            logger.debug( 'OK: wikEdDiff unit test passed: diff consistent with old text.' );


    ##
    ## Dump blocks object to browser console.
    ##
    ## @param string name Block name
    ## @param[in] array blocks Blocks table object
    ##
    def debugBlocks( self, name, blocks=None ):

        if blocks is None:
            blocks = self.blocks;
        dump = "\n" + "\t".join(["i", "oldBl", "newBl", "oldNm", "newNm", "oldSt", "count", "uniq", "words", "chars", "type", "sect", "group", "fixed", "moved", "text"]) + "\n"
        for i, block in enumerate(blocks):
            dump += "\t".join(map(str, [i, block.oldBlock, block.newBlock,
                    block.oldNumber, block.newNumber, block.oldStart,
                    block.count, block.unique, block.words,
                    block.chars, block.type, block.section,
                    block.group, block.fixed, block.moved,
                    self.debugShortenText( block.text )])) + "\n"
        logger.debug( name + ':\n' + dump );


    ##
    ## Dump groups object to browser console.
    ##
    ## @param string name Group name
    ## @param[in] array groups Groups table object
    ##
    def debugGroups( self, name, groups=None ):

        if groups is None:
            groups = self.groups;
        dump = "\n" + "\t".join(["i", "oldNm", "blSta", "blEnd", "uniq", "maxWo", "words", "chars", "fixed", "oldNm", "mFrom", "color"]) + "\n"
        for i, group in enumerate(groups):
            dump += "\t".join(map(str, [i, group.oldNumber, group.blockStart,
                    group.blockEnd, group.unique, group.maxWords,
                    group.words, group.chars, group.fixed,
                    group.oldNumber, group.movedFrom, group.color])) + "\n"
        logger.debug( name + ':\n' + dump );


    ##
    ## Dump fragments array to browser console.
    ##
    ## @param string name Fragments name
    ## @param[in] array fragments Fragments array
    ##
    def debugFragments( self, name ):

        fragments = self.fragments;
        dump = "\n" + "\t".join(["i", "type", "color", "text"]) + "\n"
        for i, fragment in enumerate(fragments):
            dump += "\t".join(map(str, [i, fragment.type, fragment.color,
                    self.debugShortenText( fragment.text, 120, 40 )])) + "\n"
        logger.debug( name + ':\n' + dump );


    ##
    ## Dump borders array to browser console.
    ##
    ## @param string name Arrays name
    ## @param[in] array border Match border array
    ##
    def debugBorders( self, name, borders ):

        dump = '\ni \t[ new \told ]\n';
        for i, border in enumerate(borders):
            dump += str(i) + ' \t[ ' + str(borders[i][0]) + ' \t' + str(borders[i][1]) + ' ]\n';
        logger.debug( name, dump );


    ##
    ## Shorten text for dumping.
    ##
    ## @param string text Text to be shortened
    ## @param int max Max length of (shortened) text
    ## @param int end Length of trailing fragment of shortened text
    ## @return string Shortened text
    ##
    def debugShortenText( self, text, max=50, end=15 ):

        if not isinstance(text, str):
            text = str(text)
        text = text.replace("\n", '\\n');
        text = text.replace("\t", '  ');
        if len(text) > max:
            text = text[ : max - 1 - end ] + '…' + text[ len(text) - end : ];
        return '"' + text + '"';


    ##
    ## Start timer 'label', analogous to JavaScript console timer.
    ## Usage: self.time( 'label' );
    ##
    ## @param string label Timer label
    ## @param[out] array timer Current time in milliseconds (float)
    ##
    def time( self, label ):

        self.timer[label] = time.time();


    ##
    ## Stop timer 'label', analogous to JavaScript console timer.
    ## Logs time in milliseconds since start to browser console.
    ## Usage: self.timeEnd( 'label' );
    ##
    ## @param string label Timer label
    ## @param bool noLog Do not log result
    ## @return float Time in milliseconds
    ##
    def timeEnd( self, label, noLog=False ):

        diff = 0;
        if label in self.timer:
            start = self.timer[label];
            stop = time.time();
            diff = stop - start;
            del self.timer[label]
            if noLog is not True:
                logger.debug( "{}: {:.2g} s".format(label, diff) )
        return diff;


    ##
    ## Log recursion timer results to browser console.
    ## Usage: self.timeRecursionEnd();
    ##
    ## @param string text Text label for output
    ## @param[in] array recursionTimer Accumulated recursion times
    ##
    def timeRecursionEnd( self, text ):

        if len(self.recursionTimer) > 1:
            # TODO: WTF? (they are accumulated first..)
            # Subtract times spent in deeper recursions
            timerEnd = len(self.recursionTimer) - 1;
            for i in range(timerEnd):
                self.recursionTimer[i] -= self.recursionTimer[i + 1];

            # Log recursion times
            for i in range(len(self.recursionTimer)):
                logger.debug( "{} recursion {}: {:.2g} s".format(text, i, self.recursionTimer[i]) )

        self.recursionTimer.clear()


    ##
    ## Log variable values to debug console.
    ## Usage: self.debug( 'var', var );
    ##
    ## @param string name Object identifier
    ## @param mixed|undefined name Object to be logged
    ##
    def debug( self, name, obj=None ):

        if obj is None:
            logger.debug( name );
        else:
            logger.debug( name + ': ' + obj );


    ##
    ## Recursive deep copy from target over source for customization import.
    ##
    ## @param object source Source object
    ## @param object target Target object
    ##
    @staticmethod
    def deepCopy( source, target ):
        if not isinstance(source, dict) or not isinstance(target, dict):
            raise TypeError("both 'source' and 'destination' must be of type 'dict'")
        for key, value in source.items():
            if isinstance(value, dict):
                node = target.setdefault(key, {})
                self.deepCopy(value, node)
            elif isinstance(value, list):
                node = target.setdefault(key, [])
                node.extend(value)
            else:
                target[key] = value


##
## Data and methods for single text version (old or new one).
##
## @class WikEdDiffText
##
class WikEdDiffText:
    
    ##
    ## Constructor, initialize text object.
    ##
    ## @param string text Text of version
    ## @param WikEdDiff parent Parent, for configuration settings and debugging methods
    ##
    def __init__( self, text, parent ):

        # @var WikEdDiff parent Parent object for configuration settings and debugging methods
        self.parent = parent;

        # @var string text Text of this version
        self.text = str(text);

        # @var array tokens Tokens list
        self.tokens = [];

        # @var int first, last First and last index of tokens list
        self.first = None;
        self.last = None;

        # @var array words Word counts for version text
        self.words = {};


        # Parse and count words and chunks for identification of unique real words
        if self.parent.config.timer is True:
            self.parent.time( 'wordParse' );
        self.wordParse( self.parent.config.regExp.countWords );
        self.wordParse( self.parent.config.regExp.countChunks );
        if self.parent.config.timer is True:
            self.parent.timeEnd( 'wordParse' );


    ##
    ## Parse and count words and chunks for identification of unique words.
    ##
    ## @param string regExp Regular expression for counting words
    ## @param[in] string text Text of version
    ## @param[out] array words Number of word occurrences
    ##
    def wordParse( self, regExp ):

        for regExpMatch in regExp.finditer(self.text):
            word = regExpMatch.group();
            self.words.setdefault(word, 0)
            self.words[word] += 1;


    ##
    ## Split text into paragraph, line, sentence, chunk, word, or character tokens.
    ##
    ## @param string level Level of splitting: paragraph, line, sentence, chunk, word, or character
    ## @param int|None token Index of token to be split, otherwise uses full text
    ## @param[in] string text Full text to be split
    ## @param[out] array tokens Tokens list
    ## @param[out] int first, last First and last index of tokens list
    ##
    def splitText( self, level, token=None ):

        current = len(self.tokens)
        first = current;

        # Split full text or specified token
        if token is None:
            prev = None;
            next = None;
            text = self.text;
        else:
            prev = self.tokens[token].prev;
            next = self.tokens[token].next;
            text = self.tokens[token].token;

        # Split text into tokens, regExp match as separator
        number = 0;
        split = [];
        lastIndex = 0;
        regExp = self.parent.config.regExp.split[level];
        for regExpMatch in regExp.finditer(text):
            if regExpMatch.start() > lastIndex:
                split.append( text[lastIndex : regExpMatch.start()] )
            split.append(regExpMatch.group())
            lastIndex = regExpMatch.end()
        if lastIndex < len(text):
            split.append( text[ lastIndex: ] );

        # Cycle through new tokens
        for i in range(len(split)):
            # Insert current item, link to previous
            self.tokens.append( Token(
                    token  = split[i],
                    prev   = prev,
                    next   = None,
                    link   = None,
                    number = None,
                    unique = False
            ) )
            number += 1;

            # Link previous item to current
            if prev is not None:
                self.tokens[prev].next = current;
            prev = current;
            current += 1;

        # Connect last new item and existing next item
        if number > 0 and token is not None:
            if prev is not None:
                self.tokens[prev].next = next;
            if next is not None:
                self.tokens[next].prev = prev;

        # Set text first and last token index
        if number > 0:
            # Initial text split
            if token is None:
                self.first = 0;
                self.last = prev;

            # First or last token has been split
            else:
                if token == self.first:
                    self.first = first;
                if token == self.last:
                    self.last = prev;


    ##
    ## Split unique unmatched tokens into smaller tokens.
    ##
    ## @param string level Level of splitting: line, sentence, chunk, or word
    ## @param[in] array tokens Tokens list
    ##
    def splitRefine( self, regExp ):

        # Cycle through tokens list
        i = self.first;
        while i is not None:
            # Refine unique unmatched tokens into smaller tokens
            if self.tokens[i].link is None:
                self.splitText( regExp, i );
            i = self.tokens[i].next;


    ##
    ## Enumerate text token list before detecting blocks.
    ##
    ## @param[out] array tokens Tokens list
    ##
    def enumerateTokens(self):

        # Enumerate tokens list
        number = 0;
        i = self.first;
        while i is not None:
            self.tokens[i].number = number;
            number += 1;
            i = self.tokens[i].next;


    ##
    ## Dump tokens object to browser console.
    ##
    ## @param string name Text name
    ## @param[in] int first, last First and last index of tokens list
    ## @param[in] array tokens Tokens list
    ##
    def debugText( self, name ):

        tokens = self.tokens;
        dump = 'first: ' + str(self.first) + '\tlast: ' + str(self.last) + '\n';
        dump += '\ni \tlink \t(prev \tnext) \tuniq \t#num \t"token"\n';
        i = self.first;
        while i is not None:
            dump += "{} \t{} \t({} \t{}) \t{} \t#{} \t{}\n".format(i, tokens[i].link, tokens[i].prev, tokens[i].next,
                                                                   tokens[i].unique, tokens[i].number,
                                                                   self.parent.debugShortenText( tokens[i].token ))
            i = tokens[i].next;
        logger.debug( name + ':\n' + dump );

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("usage: {} old_file new_file".format(sys.argv[0]))
        sys.exit(1)

    def setTerminalLogging():
        # create console handler and set level
        handler = logging.StreamHandler()

        # create formatter
        formatter = logging.Formatter("{message}", style="{")
        handler.setFormatter(formatter)

        # add the handler to the root logger
        logger = logging.getLogger()
        logger.addHandler(handler)

        return logger

    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)

    setTerminalLogging()

    f1 = open(sys.argv[1], "r")
    f2 = open(sys.argv[2], "r")

    config = WikedDiffConfig()
    wd = WikEdDiff(config)
    html = wd.diff(f1.read(), f2.read())

    template = """
<?xml version="1.0" encoding="UTF-8"?>
<!doctype html>
<html>
<head>
<meta charset="UTF-8">
<title>{title}</title>
<script id="wikEdDiffBlockHandler">
{script}
</script>
<style type="text/css" id="wikEdDiffStyles">
{stylesheet}
</style>
</head>
<body>
{diff}
</body>
</html>
"""

    javascript = """
var wikEdDiffBlockHandler = function ( event, element, type ) {

        // IE compatibility
        if ( event === undefined && window.event !== undefined ) {
                event = window.event;
        }

        // Get mark/block elements
        var number = element.id.replace( /\D/g, '' );
        var block = document.getElementById( 'wikEdDiffBlock' + number );
        var mark = document.getElementById( 'wikEdDiffMark' + number );
        if ( block === null || mark === null ) {
                return;
        }

        // Highlight corresponding mark/block pairs
        if ( type === 'mouseover' ) {
                element.onmouseover = null;
                element.onmouseout = function ( event ) {
                        window.wikEdDiffBlockHandler( event, element, 'mouseout' );
                };
                element.onclick = function ( event ) {
                        window.wikEdDiffBlockHandler( event, element, 'click' );
                };
                block.className += ' wikEdDiffBlockHighlight';
                mark.className += ' wikEdDiffMarkHighlight';
        }

        // Remove mark/block highlighting
        if ( type === 'mouseout' || type === 'click' ) {
                element.onmouseout = null;
                element.onmouseover = function ( event ) {
                        window.wikEdDiffBlockHandler( event, element, 'mouseover' );
                };

                // Reset, allow outside container (e.g. legend)
                if ( type !== 'click' ) {
                        block.className = block.className.replace( / wikEdDiffBlockHighlight/g, '' );
                        mark.className = mark.className.replace( / wikEdDiffMarkHighlight/g, '' );

                        // GetElementsByClassName
                        var container = document.getElementById( 'wikEdDiffContainer' );
                        if ( container !== null ) {
                                var spans = container.getElementsByTagName( 'span' );
                                var spansLength = spans.length;
                                for ( var i = 0; i < spansLength; i ++ ) {
                                        if ( spans[i] !== block && spans[i] !== mark ) {
                                                if ( spans[i].className.indexOf( ' wikEdDiffBlockHighlight' ) !== -1 ) {
                                                        spans[i].className = spans[i].className.replace( / wikEdDiffBlockHighlight/g, '' );
                                                }
                                                else if ( spans[i].className.indexOf( ' wikEdDiffMarkHighlight') !== -1 ) {
                                                        spans[i].className = spans[i].className.replace( / wikEdDiffMarkHighlight/g, '' );
                                                }
                                        }
                                }
                        }
                }
        }

        // Scroll to corresponding mark/block element
        if ( type === 'click' ) {

                // Get corresponding element
                var corrElement;
                if ( element === block ) {
                        corrElement = mark;
                }
                else {
                        corrElement = block;
                }

                // Get element height (getOffsetTop)
                var corrElementPos = 0;
                var node = corrElement;
                do {
                        corrElementPos += node.offsetTop;
                } while ( ( node = node.offsetParent ) !== null );

                // Get scroll height
                var top;
                if ( window.pageYOffset !== undefined ) {
                        top = window.pageYOffset;
                }
                else {
                        top = document.documentElement.scrollTop;
                }

                // Get cursor pos
                var cursor;
                if ( event.pageY !== undefined ) {
                        cursor = event.pageY;
                }
                else if ( event.clientY !== undefined ) {
                        cursor = event.clientY + top;
                }

                // Get line height
                var line = 12;
                if ( window.getComputedStyle !== undefined ) {
                        line = parseInt( window.getComputedStyle( corrElement ).getPropertyValue( 'line-height' ) );
                }

                // Scroll element under mouse cursor
                window.scroll( 0, corrElementPos + top - cursor + line / 2 );
        }
        return;
};
"""
    
    # Replace mark symbols
    stylesheet = config.stylesheet.replace("{cssMarkLeft}", config.cssMarkLeft) \
                                  .replace("{cssMarkRight}", config.cssMarkRight)

    out = open("output.html", "w")
    out.write(template.format(title=sys.argv[2], script=javascript, stylesheet=stylesheet, diff=html))
