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

Notable differences between the Python port and the original JavaScript version:

 - The HTML formatter has been split from the main `WikEdDiff` class into a
   separate submodule, along with corresponding settings from the
   `WikEdDiffConfig` class.
 - Added an ANSI color formatter and a console demo script (`wikeddiff`).

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
  .newText              new text
  .oldText              old text
  .maxWords             word count of longest linked block
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

from .utils import *
from .data_structures import *

logger = logging.getLogger(__name__)

__all__ = ["WikEdDiff"]

##
## wikEd diff main class.
##
## @class WikEdDiff
##
class WikEdDiff:

    ##
    ## Constructor, initialize settings.
    ##
    ## @param WikEdDiffConfig config Custom customization settings
    ##
    def __init__(self, config):

        self.config = config

        # Internal data structures.

        # @var WikEdDiffText newText New text version object with text and token list
        self.newText = None

        # @var WikEdDiffText oldText Old text version object with text and token list
        self.oldText = None

        # @var Symbols symbols Symbols table for whole text at all refinement levels
        self.symbols = Symbols(token=[], hashTable={}, linked=False)

        # @var array bordersDown Matched region borders downwards
        self.bordersDown = []

        # @var array bordersUp Matched region borders upwards
        self.bordersUp = []

        # @var array blocks Block data (consecutive text tokens) in new text order
        self.blocks = []

        # @var int maxWords Maximal detected word count of all linked blocks
        self.maxWords = 0

        # @var array groups Section blocks that are consecutive in old text order
        self.groups = []

        # @var array sections Block sections with no block move crosses outside a section
        self.sections = []

        # @var object timer Debug timer array: string 'label' => float milliseconds.
        self.timer = {}

        # @var array recursionTimer Count time spent in recursion level in milliseconds.
        self.recursionTimer = {}

        # Output data.

        # @var bool error Unit tests have detected a diff error
        self.error = False


    ##
    ## Main diff method producing a list of fragments ready for markup,
    ## which serves as an abstraction layer for diffs.
    ##
    ## @param string oldString Old text version
    ## @param string newString New text version
    ## @return array fragments: A list of Fragment objects
    ##
    def diff( self, oldString, newString ):

        if self.config.timer is True:
            # Start total timer
            self.time( 'total' )
            # Start diff timer
            self.time( 'diff' )

        # Reset error flag
        self.error = False

        # Strip trailing newline (.js only)
        if self.config.stripTrailingNewline is True:
            if newString.endswith('\n') and oldString.endswith('\n'):
                newString = newString[:-1]
                oldString = oldString[:-1]

        # Load version strings into WikEdDiffText objects
        self.newText = WikEdDiffText( newString, self )
        self.oldText = WikEdDiffText( oldString, self )

        # Trap trivial changes: no change
        if self.newText.text == self.oldText.text:
            fragments = []
            fragments.append( Fragment( text='', type='{', color=0 ) )
            fragments.append( Fragment( text='', type='[', color=0 ) )
            fragments.append( Fragment( text='', type='=', color=0 ) )
            fragments.append( Fragment( text='', type=']', color=0 ) )
            fragments.append( Fragment( text='', type='}', color=0 ) )
            return fragments

        # Split new and old text into paragraps
        if self.config.timer is True:
            self.time( 'paragraph split' )
        self.newText.splitText( 'paragraph' )
        self.oldText.splitText( 'paragraph' )
        if self.config.timer is True:
            self.timeEnd( 'paragraph split' )

        # Calculate diff
        self.calculateDiff( 'line' )

        # Refine different paragraphs into lines
        if self.config.timer is True:
            self.time( 'line split' )
        self.newText.splitRefine( 'line' )
        self.oldText.splitRefine( 'line' )
        if self.config.timer is True:
            self.timeEnd( 'line split' )

        # Calculate refined diff
        self.calculateDiff( 'line' )

        # Refine different lines into sentences
        if self.config.timer is True:
            self.time( 'sentence split' )
        self.newText.splitRefine( 'sentence' )
        self.oldText.splitRefine( 'sentence' )
        if self.config.timer is True:
            self.timeEnd( 'sentence split' )

        # Calculate refined diff
        self.calculateDiff( 'sentence' )

        # Refine different sentences into chunks
        if self.config.timer is True:
            self.time( 'chunk split' )
        self.newText.splitRefine( 'chunk' )
        self.oldText.splitRefine( 'chunk' )
        if self.config.timer is True:
            self.timeEnd( 'chunk split' )

        # Calculate refined diff
        self.calculateDiff( 'chunk' )

        # Refine different chunks into words
        if self.config.timer is True:
            self.time( 'word split' )
        self.newText.splitRefine( 'word' )
        self.oldText.splitRefine( 'word' )
        if self.config.timer is True:
            self.timeEnd( 'word split' )

        # Calculate refined diff information with recursion for unresolved gaps
        self.calculateDiff( 'word', True )

        # Slide gaps
        if self.config.timer is True:
            self.time( 'word slide' )
        self.slideGaps( self.newText, self.oldText )
        self.slideGaps( self.oldText, self.newText )
        if self.config.timer is True:
            self.timeEnd( 'word slide' )

        # Split tokens into chars
        if self.config.charDiff is True:
            # Split tokens into chars in selected unresolved gaps
            if self.config.timer is True:
                self.time( 'character split' )
            self.splitRefineChars()
            if self.config.timer is True:
                self.timeEnd( 'character split' )

            # Calculate refined diff information with recursion for unresolved gaps
            self.calculateDiff( 'character', True )

            # Slide gaps
            if self.config.timer is True:
                self.time( 'character slide' )
            self.slideGaps( self.newText, self.oldText )
            self.slideGaps( self.oldText, self.newText )
            if self.config.timer is True:
                self.timeEnd( 'character slide' )

        # Free memory
        self.symbols = Symbols(token=[], hashTable={}, linked=False)
        self.bordersDown.clear()
        self.bordersUp.clear()
        self.newText.words.clear()
        self.oldText.words.clear()

        # Enumerate token lists
        self.newText.enumerateTokens()
        self.oldText.enumerateTokens()

        # Detect moved blocks
        if self.config.timer is True:
            self.time( 'blocks' )
        self.detectBlocks()
        if self.config.timer is True:
            self.timeEnd( 'blocks' )

        # Free memory
        self.newText.tokens.clear()
        self.oldText.tokens.clear()

        # Assemble blocks into fragment table
        fragments = self.getDiffFragments()

        # Free memory
        self.blocks.clear()
        self.groups.clear()
        self.sections.clear()

        # Stop diff timer
        if self.config.timer is True:
            self.timeEnd( 'diff' )

        # Unit tests
        if self.config.unitTesting is True:
            # Test diff to test consistency between input and output
            if self.config.timer is True:
                self.time( 'unit tests' )
            self.unitTests( self.oldText, self.newText, fragments )
            if self.config.timer is True:
                self.timeEnd( 'unit tests' )

        # Debug log
        if self.config.debug is True:
            self.debugFragments( 'Fragments before clipping', fragments )

        # Clipping
        if self.config.fullDiff is False:
            # Clipping unchanged sections from unmoved block text
            if self.config.timer is True:
                self.time( 'clip' )
            self.clipDiffFragments( fragments )
            if self.config.timer is True:
                self.timeEnd( 'clip' )

        # Debug log
        if self.config.debug is True:
            self.debugFragments( 'Fragments', fragments )

        # Stop total timer
        if self.config.timer is True:
            self.timeEnd( 'total' )

        return fragments


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
        gaps = []
        gap = None
        i = self.newText.first
        j = self.oldText.first
        while i is not None:
            # Get token links
            newLink = self.newText.tokens[i].link
            oldLink = None
            if j is not None:
                oldLink = self.oldText.tokens[j].link

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
                gaps[gap].newLast = i
                gaps[gap].newTokens += 1

            # Gap ended
            elif gap is not None and newLink is not None:
                gap = None

            # Next list elements
            if newLink is not None:
                j = self.oldText.tokens[newLink].next
            i = self.newText.tokens[i].next

        # Cycle through gaps and add old text gap data
        for gap in gaps:
            # Cycle through old text tokens list
            j = gap.oldFirst
            while (
                    j is not None and
                    self.oldText.tokens[j] is not None and
                    self.oldText.tokens[j].link is None
                    ):
                # Count old chars and tokens in gap
                gap.oldLast = j
                gap.oldTokens += 1

                j = self.oldText.tokens[j].next

        # Select gaps of identical token number and strong similarity of all tokens.
        for gap in gaps:
            charSplit = True

            # Not same gap length
            if gap.newTokens != gap.oldTokens:
                # One word became separated by space, dash, or any string
                if gap.newTokens == 1 and gap.oldTokens == 3:
                    token = self.newText.tokens[ gap.newFirst ].token
                    tokenFirst = self.oldText.tokens[ gap.oldFirst ].token
                    tokenLast = self.oldText.tokens[ gap.oldLast ].token
                    if not token.startswith(tokenFirst) or not token.endswith(tokenLast):
                        continue
                elif gap.oldTokens == 1 and gap.newTokens == 3:
                    token = self.oldText.tokens[ gap.oldFirst ].token
                    tokenFirst = self.newText.tokens[ gap.newFirst ].token
                    tokenLast = self.newText.tokens[ gap.newLast ].token
                    if not token.startswith(tokenFirst) or not token.endswith(tokenLast):
                        continue
                else:
                    continue
                gap.charSplit = True

            # Cycle through new text tokens list and set charSplit
            else:
                i = gap.newFirst
                j = gap.oldFirst
                while i is not None:
                    newToken = self.newText.tokens[i].token
                    oldToken = self.oldText.tokens[j].token

                    # Get shorter and longer token
                    if len(newToken) < len(oldToken):
                        shorterToken = newToken
                        longerToken = oldToken
                    else:
                        shorterToken = oldToken
                        longerToken = newToken

                    # Not same token length
                    if len(newToken) != len(oldToken):

                        # Test for addition or deletion of internal string in tokens

                        # Find number of identical chars from left
                        left = 0
                        while left < len(shorterToken):
                            if newToken[ left ] != oldToken[ left ]:
                                break
                            left += 1

                        # Find number of identical chars from right
                        right = 0
                        while right < len(shorterToken):
                            if (
                                    newToken[ len(newToken) - 1 - right ] !=
                                    oldToken[ len(oldToken) - 1 - right ]
                                    ):
                                break
                            right += 1

                        # No simple insertion or deletion of internal string
                        if left + right != len(shorterToken):
                            # Not addition or deletion of flanking strings in tokens
                            # Smaller token not part of larger token
                            if shorterToken not in longerToken:
                                # Same text at start or end shorter than different text
                                if left < len(shorterToken) / 2 and right < len(shorterToken) / 2:
                                    # Do not split into chars in this gap
                                    charSplit = False
                                    break

                    # Same token length
                    elif newToken != oldToken:
                        # Tokens less than 50 % identical
                        ident = 0
                        for pos in range(len(shorterToken)):
                            if shorterToken[ pos ] == longerToken[ pos ]:
                                ident += 1
                        if ident / len(shorterToken) < 0.49:
                            # Do not split into chars this gap
                            charSplit = False
                            break

                    # Next list elements
                    if i == gap.newLast:
                        break
                    i = self.newText.tokens[i].next
                    j = self.oldText.tokens[j].next
                gap.charSplit = charSplit

        # Refine words into chars in selected gaps.
        for gap in gaps:
            if gap.charSplit is True:

                # Cycle through new text tokens list, link spaces, and split into chars
                i = gap.newFirst
                j = gap.oldFirst
                newGapLength = i - gap.newLast
                oldGapLength = j - gap.oldLast
                while i is not None or j is not None:

                    # Link identical tokens (spaces) to keep char refinement to words
                    if (
                            newGapLength == oldGapLength and
                            self.newText.tokens[i].token == self.oldText.tokens[j].token
                            ):
                        self.newText.tokens[i].link = j
                        self.oldText.tokens[j].link = i

                    # Refine words into chars
                    else:
                        if i is not None:
                            self.newText.splitText( 'character', i )
                        if j is not None:
                            self.oldText.splitText( 'character', j )

                    # Next list elements
                    if i == gap.newLast:
                        i = None
                    if j == gap.oldLast:
                        j = None
                    if i is not None:
                        i = self.newText.tokens[i].next
                    if j is not None:
                        j = self.oldText.tokens[j].next


    ##
    ## Move gaps with ambiguous identical fronts to last newline border or otherwise last word border.
    ##
    ## @param[in/out] wikEdDiffText text, textLinked These two are newText and oldText
    ##
    def slideGaps( self, text, textLinked ):

        regExpSlideBorder = self.config.regExp.slideBorder
        regExpSlideStop = self.config.regExp.slideStop

        # Cycle through tokens list
        i = text.first
        gapStart = None
        while i is not None:

            # Remember gap start
            if gapStart is None and text.tokens[i].link is None:
                gapStart = i

            # Find gap end
            elif gapStart is not None and text.tokens[i].link is not None:
                gapFront = gapStart
                gapBack = text.tokens[i].prev

                # Slide down as deep as possible
                front = gapFront
                back = text.tokens[gapBack].next
                if (
                        front is not None and
                        back is not None and
                        text.tokens[front].link is None and
                        text.tokens[back].link is not None and
                        text.tokens[front].token == text.tokens[back].token
                        ):
                    text.tokens[front].link = text.tokens[back].link
                    textLinked.tokens[ text.tokens[front].link ].link = front
                    text.tokens[back].link = None

                    gapFront = text.tokens[gapFront].next
                    gapBack = text.tokens[gapBack].next

                    front = text.tokens[front].next
                    back = text.tokens[back].next

                # Test slide up, remember last line break or word border
                front = text.tokens[gapFront].prev
                back = gapBack
                gapFrontBlankTest = regExpSlideBorder.search( text.tokens[gapFront].token )
                frontStop = front
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
                                frontStop = front
                                break

# TODO: does this work? (comparison of re.match objects)
                            # Stop at first word border (blank/word or word/blank)
                            if regExpSlideBorder.search( text.tokens[front].token ) != gapFrontBlankTest:
                                frontStop = front
                        front = text.tokens[front].prev
                        back = text.tokens[back].prev

                # Actually slide up to stop
                front = text.tokens[gapFront].prev
                back = gapBack
                while (
                        front is not None and
                        back is not None and
                        front != frontStop and
                        text.tokens[front].link is not None and
                        text.tokens[back].link is None and
                        text.tokens[front].token == text.tokens[back].token
                        ):
                    text.tokens[back].link = text.tokens[front].link
                    textLinked.tokens[ text.tokens[back].link ].link = back
                    text.tokens[front].link = None

                    front = text.tokens[front].prev
                    back = text.tokens[back].prev
                gapStart = None
            i = text.tokens[i].next


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
            self.time( level )
        if self.config.timer is True and repeating is False:
            self.time( level + str(recursionLevel) )

        # Get object symbols table and linked region borders
        if recursionLevel == 0 and repeating is False:
            symbols = self.symbols
            bordersDown = self.bordersDown
            bordersUp = self.bordersUp

        # Create empty local symbols table and linked region borders arrays
        else:
            symbols = Symbols(token=[], hashTable={}, linked=False)
            bordersDown = []
            bordersUp = []

        # Updated versions of linked region borders
        bordersUpNext = []
        bordersDownNext = []

        ##
        ## Pass 1: parse new text into symbol table.
        ##

        # Cycle through new text tokens list
        i = newStart
        while i is not None:
            if self.newText.tokens[i].link is None:
                # Add new entry to symbol table
                token = self.newText.tokens[i].token
                if token not in symbols.hashTable:
                    symbols.hashTable[token] = len(symbols.token)
                    symbols.token.append( Symbol(
                            newCount=1,
                            oldCount=0,
                            newToken=i,
                            oldToken=None
                    ) )

                # Or update existing entry
                else:
                    # Increment token counter for new text
                    hashToArray = symbols.hashTable[token]
                    symbols.token[hashToArray].newCount += 1

            # Stop after gap if recursing
            elif recursionLevel > 0:
                break

            # Get next token
            if up is False:
                i = self.newText.tokens[i].next
            else:
                i = self.newText.tokens[i].prev

        ##
        ## Pass 2: parse old text into symbol table.
        ##

        # Cycle through old text tokens list
        j = oldStart
        while j is not None:
            if self.oldText.tokens[j].link is None:
                # Add new entry to symbol table
                token = self.oldText.tokens[j].token
                if token not in symbols.hashTable:
                    symbols.hashTable[token] = len(symbols.token)
                    symbols.token.append( Symbol(
                            newCount=0,
                            oldCount=1,
                            newToken=None,
                            oldToken=j
                    ) )

                # Or update existing entry
                else:
                    # Increment token counter for old text
                    hashToArray = symbols.hashTable[token]
                    symbols.token[hashToArray].oldCount += 1

                    # Add token number for old text
                    symbols.token[hashToArray].oldToken = j

            # Stop after gap if recursing
            elif recursionLevel > 0:
                break

            # Get next token
            if up is False:
                j = self.oldText.tokens[j].next
            else:
                j = self.oldText.tokens[j].prev

        ##
        ## Pass 3: connect unique tokens.
        ##

        # Cycle through symbol array
        for symbolToken in symbols.token:
            # Find tokens in the symbol table that occur only once in both versions
            if symbolToken.newCount == 1 and symbolToken.oldCount == 1:
                newToken = symbolToken.newToken
                oldToken = symbolToken.oldToken
                newTokenObj = self.newText.tokens[newToken]
                oldTokenObj = self.oldText.tokens[oldToken]

                # Connect from new to old and from old to new
                if newTokenObj.link is None:
                    # Do not use spaces as unique markers
                    if self.config.regExp.blankOnlyToken.search( newTokenObj.token ):
                        # Link new and old tokens
                        newTokenObj.link = oldToken
                        oldTokenObj.link = newToken
                        symbols.linked = True

                        # Save linked region borders
                        bordersDown.append( [newToken, oldToken] )
                        bordersUp.append( [newToken, oldToken] )

                        # Check if token contains unique word
                        if recursionLevel == 0:
                            unique = False
                            if level == 'character':
                                unique = True
                            else:
                                token = newTokenObj.token
                                wordsGen = itertools.chain( self.config.regExp.countWords.finditer(token),
                                                            self.config.regExp.countChunks.finditer(token) )
                                words = [match.group() for match in wordsGen]

                                # Unique if longer than min block length
                                if len(words) >= self.config.blockMinLength:
                                    unique = True

                                # Unique if it contains at least one unique word
                                else:
                                    for word in words:
                                        if (
                                                word in self.oldText.words and
                                                word in self.newText.words and
                                                self.oldText.words[word] == 1 and
                                                self.newText.words[word] == 1
                                                ):
                                            unique = True
                                            break

                            # Set unique
                            if unique is True:
                                newTokenObj.unique = True
                                oldTokenObj.unique = True

        # Continue passes only if unique tokens have been linked previously
        if symbols.linked is True:

            ##
            ## Pass 4: connect adjacent identical tokens downwards.
            ##

            # Cycle through list of linked new text tokens
            for border in bordersDown:
                i = border[0]
                j = border[1]

                # Next down
                iMatch = i
                jMatch = j
                i = self.newText.tokens[i].next
                j = self.oldText.tokens[j].next

                # Cycle through new text list gap region downwards
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None
                        ):

                    # Connect if same token
                    if self.newText.tokens[i].token == self.oldText.tokens[j].token:
                        self.newText.tokens[i].link = j
                        self.oldText.tokens[j].link = i

                    # Not a match yet, maybe in next refinement level
                    else:
                        bordersDownNext.append( [iMatch, jMatch] )
                        break

                    # Next token down
                    iMatch = i
                    jMatch = j
                    i = self.newText.tokens[i].next
                    j = self.oldText.tokens[j].next

            ##
            ## Pass 5: connect adjacent identical tokens upwards.
            ##

            # Cycle through list of connected new text tokens
            for border in bordersUp:
                i = border[0]
                j = border[1]

                # Next up
                iMatch = i
                jMatch = j
                i = self.newText.tokens[i].prev
                j = self.oldText.tokens[j].prev

                # Cycle through new text gap region upwards
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None
                        ):

                    # Connect if same token
                    if self.newText.tokens[i].token == self.oldText.tokens[j].token:
                        self.newText.tokens[i].link = j
                        self.oldText.tokens[j].link = i

                    # Not a match yet, maybe in next refinement level
                    else:
                        bordersUpNext.append( [iMatch, jMatch] )
                        break

                    # Next token up
                    iMatch = i
                    jMatch = j
                    i = self.newText.tokens[i].prev
                    j = self.oldText.tokens[j].prev

            ##
            ## Connect adjacent identical tokens downwards from text start.
            ## Treat boundary as connected, stop after first connected token.
            ##

            # Only for full text diff
            if recursionLevel == 0 and repeating is False:
                # From start
                i = self.newText.first
                j = self.oldText.first
                iMatch = None
                jMatch = None

                # Cycle through old text tokens down
                # Connect identical tokens, stop after first connected token
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None and
                        self.newText.tokens[i].token == self.oldText.tokens[j].token
                        ):
                    self.newText.tokens[i].link = j
                    self.oldText.tokens[j].link = i
                    iMatch = i
                    jMatch = j
                    i = self.newText.tokens[i].next
                    j = self.oldText.tokens[j].next
                if iMatch is not None:
                    bordersDownNext.append( [iMatch, jMatch] )

                # From end
                i = self.newText.last
                j = self.oldText.last
                iMatch = None
                jMatch = None

                # Cycle through old text tokens up
                # Connect identical tokens, stop after first connected token
                while (
                        i is not None and
                        j is not None and
                        self.newText.tokens[i].link is None and
                        self.oldText.tokens[j].link is None and
                        self.newText.tokens[i].token == self.oldText.tokens[j].token
                        ):
                    self.newText.tokens[i].link = j
                    self.oldText.tokens[j].link = i
                    iMatch = i
                    jMatch = j
                    i = self.newText.tokens[i].prev
                    j = self.oldText.tokens[j].prev
                if iMatch is not None:
                    bordersUpNext.append( [iMatch, jMatch] )

            # Save updated linked region borders to object
            if recursionLevel == 0 and repeating is False:
                self.bordersDown = bordersDownNext
                self.bordersUp = bordersUpNext

            # Merge local updated linked region borders into object
            else:
                self.bordersDown += bordersDownNext
                self.bordersUp += bordersUpNext


            ##
            ## Repeat once with empty symbol table to link hidden unresolved common tokens in cross-overs.
            ## ("and" in "and this a and b that" -> "and this a and b that")
            ##

            if repeating is False and self.config.repeatedDiff is True:
                repeat = True
                self.calculateDiff( level, recurse, repeat, newStart, oldStart, up, recursionLevel )

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
                    i = border[0]
                    j = border[1]

                    # Next token down
                    i = self.newText.tokens[i].next
                    j = self.oldText.tokens[j].next

                    # Start recursion at first gap token pair
                    if (
                            i is not None and
                            j is not None and
                            self.newText.tokens[i].link is None and
                            self.oldText.tokens[j].link is None
                            ):
                        repeat = False
                        dirUp = False
                        self.calculateDiff( level, recurse, repeat, i, j, dirUp, recursionLevel + 1 )

                ##
                ## Recursively diff gap upwards.
                ##

                # Cycle through list of linked region borders
                for border in bordersUpNext:
                    i = border[0]
                    j = border[1]

                    # Next token up
                    i = self.newText.tokens[i].prev
                    j = self.oldText.tokens[j].prev

                    # Start recursion at first gap token pair
                    if (
                            i is not None and
                            j is not None and
                            self.newText.tokens[i].link is None and
                            self.oldText.tokens[j].link is None
                            ):
                        repeat = False
                        dirUp = True
                        self.calculateDiff( level, recurse, repeat, i, j, dirUp, recursionLevel + 1 )

        # Stop timers
        if self.config.timer is True and repeating is False:
            self.recursionTimer.setdefault(recursionLevel, 0.0)
            self.recursionTimer[recursionLevel] += self.timeEnd( level + str(recursionLevel), True )
        if self.config.timer is True and repeating is False and recursionLevel == 0:
            self.timeRecursionEnd( level )
            self.timeEnd( level )


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
            self.oldText.debugText( 'Old text' )
            self.newText.debugText( 'New text' )

        # Collect identical corresponding ('=') blocks from old text and sort by new text
        self.getSameBlocks()

        # Collect independent block sections with no block move crosses outside a section
        self.getSections()

        # Find groups of continuous old text blocks
        self.getGroups()

        # Set longest sequence of increasing groups in sections as fixed (not moved)
        self.setFixed()

        # Convert groups to insertions/deletions if maximum block length is too short
        # Only for more complex texts that actually have blocks of minimum block length
        unlinkCount = 0
        if (
                self.config.unlinkBlocks is True and
                self.config.blockMinLength > 0 and
                self.maxWords >= self.config.blockMinLength
                ):
            if self.config.timer is True:
                self.time( 'total unlinking' )

            # Repeat as long as unlinking is possible
            unlinked = True
            while unlinked is True and unlinkCount < self.config.unlinkMax:
                # Convert '=' to '+'/'-' pairs
                unlinked = self.unlinkBlocks()

                # Start over after conversion
                if unlinked is True:
                    unlinkCount += 1
                    self.slideGaps( self.newText, self.oldText )
                    self.slideGaps( self.oldText, self.newText )

                    # Repeat block detection from start
                    self.maxWords = 0
                    self.getSameBlocks()
                    self.getSections()
                    self.getGroups()
                    self.setFixed()

            if self.config.timer is True:
                self.timeEnd( 'total unlinking' )

        # Collect deletion ('-') blocks from old text
        self.getDelBlocks()

        # Position '-' blocks into new text order
        self.positionDelBlocks()

        # Collect insertion ('+') blocks from new text
        self.getInsBlocks()

        # Set group numbers of '+' blocks
        self.setInsGroups()

        # Mark original positions of moved groups
        self.insertMarks()

        # Debug log
        if self.config.timer is True or self.config.debug is True:
            logger.debug( 'Unlink count: {}'.format(unlinkCount) )
        if self.config.debug is True:
            self.debugGroups( 'Groups' )
            self.debugBlocks( 'Blocks' )


    ##
    ## Collect identical corresponding matching ('=') blocks from old text and sort by new text.
    ##
    ## @param[in] WikEdDiffText newText, oldText Text objects
    ## @param[in/out] array blocks Blocks table object
    ##
    def getSameBlocks(self):

        if self.config.timer is True:
            self.time( 'getSameBlocks' )

        blocks = self.blocks

        # Clear blocks array
        blocks.clear()

        # Cycle through old text to find connected (linked, matched) blocks
        j = self.oldText.first
        i = None
        while j is not None:
            # Skip '-' blocks
            while j is not None and self.oldText.tokens[j].link is None:
                j = self.oldText.tokens[j].next

            # Get '=' block
            if j is not None:
                i = self.oldText.tokens[j].link
                iStart = i
                jStart = j

                # Detect matching blocks ('=')
                count = 0
                unique = False
                text = ''
                while i is not None and j is not None and self.oldText.tokens[j].link == i:
                    text += self.oldText.tokens[j].token
                    count += 1
                    if self.newText.tokens[i].unique is True:
                        unique = True
                    i = self.newText.tokens[i].next
                    j = self.oldText.tokens[j].next

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
            block.newBlock = i

        if self.config.timer is True:
            self.timeEnd( 'getSameBlocks' )


    ##
    ## Collect independent block sections with no block move crosses
    ## outside a section for per-section determination of non-moving fixed groups.
    ##
    ## @param[out] array sections Sections table object
    ## @param[in/out] array blocks Blocks table object, section property
    ##
    def getSections(self):

        if self.config.timer is True:
            self.time( 'getSections' )

        blocks = self.blocks
        sections = self.sections

        # Clear sections array
        sections.clear()

        # Cycle through blocks
        block = 0
        while block < len(blocks):
            sectionStart = block
            sectionEnd = block

            oldMax = blocks[sectionStart].oldNumber
            sectionOldMax = oldMax

            # Check right
            for j in range(sectionStart + 1, len(blocks)):
                # Check for crossing over to the left
                if blocks[j].oldNumber > oldMax:
                    oldMax = blocks[j].oldNumber
                elif blocks[j].oldNumber < sectionOldMax:
                    sectionEnd = j
                    sectionOldMax = oldMax

            # Save crossing sections
            if sectionEnd > sectionStart:
                # Save section to block
                for i in range(sectionStart, sectionEnd + 1):
                    blocks[i].section = len(sections)

                # Save section
                sections.append( Section(
                        blockStart = sectionStart,
                        blockEnd   = sectionEnd
                    ) )
                block = sectionEnd
                continue

            block += 1

        if self.config.timer is True:
            self.timeEnd( 'getSections' )


    ##
    ## Find groups of continuous old text blocks.
    ##
    ## @param[out] array groups Groups table object
    ## @param[in/out] array blocks Blocks table object, group property
    ##
    def getGroups(self):

        if self.config.timer is True:
            self.time( 'getGroups' )

        blocks = self.blocks
        groups = self.groups

        # Clear groups array
        groups.clear()

        # Cycle through blocks
        block = 0
        while block < len(blocks):
            groupStart = block
            groupEnd = block
            oldBlock = blocks[groupStart].oldBlock

            # Get word and char count of block
            words = self.wordCount( blocks[block].text )
            maxWords = words
            unique = blocks[block].unique
            chars = blocks[block].chars

            # Check right
            for i in range(groupEnd + 1, len(blocks)):
                # Check for crossing over to the left
                if blocks[i].oldBlock != oldBlock + 1:
                    break
                oldBlock = blocks[i].oldBlock

                # Get word and char count of block
                if blocks[i].words > maxWords:
                    maxWords = blocks[i].words
                if blocks[i].unique is True:
                    unique = True
                words += blocks[i].words
                chars += blocks[i].chars
                groupEnd = i

            # Save crossing group
            if groupEnd >= groupStart:
                # Set groups outside sections as fixed
                fixed = False
                if blocks[groupStart].section is None:
                    fixed = True

                # Save group to block
                for i in range(groupStart, groupEnd + 1):
                    blocks[i].group = len(groups)
                    blocks[i].fixed = fixed

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
                ) )
                block = groupEnd

                # Set global word count of longest linked block
                if maxWords > self.maxWords:
                    self.maxWords = maxWords

            block += 1

        if self.config.timer is True:
            self.timeEnd( 'getGroups' )


    ##
    ## Set longest sequence of increasing groups in sections as fixed (not moved).
    ##
    ## @param[in] array sections Sections table object
    ## @param[in/out] array groups Groups table object, fixed property
    ## @param[in/out] array blocks Blocks table object, fixed property
    ##
    def setFixed(self):

        if self.config.timer is True:
            self.time( 'setFixed' )

        blocks = self.blocks
        groups = self.groups
        sections = self.sections

        # Cycle through sections
        for section in sections:
            blockStart = section.blockStart
            blockEnd = section.blockEnd

            groupStart = blocks[blockStart].group
            groupEnd = blocks[blockEnd].group

            # Recusively find path of groups in increasing old group order with longest char length
            cache = {}
            maxChars = 0
            maxPath = None

            # Start at each group of section
            for i in range(groupStart, groupEnd + 1):
                pathObj = self.findMaxPath( i, groupEnd, cache )
                if pathObj.chars > maxChars:
                    maxPath = pathObj.path
                    maxChars = pathObj.chars

            # Mark fixed groups
# TODO simplify
            for i in range(len(maxPath)):
                group = maxPath[i]
                groups[group].fixed = True

                # Mark fixed blocks
                for block in range(groups[group].blockStart, groups[group].blockEnd + 1):
                    blocks[block].fixed = True

        if self.config.timer is True:
            self.timeEnd( 'setFixed' )


    ##
    ## Recusively find path of groups in increasing old group order with longest char length.
    ##
    ## @param int start Path start group
    ## @param int groupEnd Path last group
    ## @param array cache Cache object, contains returnObj for start
    ## @return array returnObj Contains path and char length
    ##
    def findMaxPath( self, start, groupEnd, cache ):

        groups = self.groups

        # Find longest sub-path
        maxChars = 0
        oldNumber = groups[start].oldNumber
        returnObj = CacheEntry( path=[], chars=0 )
        for i in range(start + 1, groupEnd + 1):
            # Only in increasing old group order
            if groups[i].oldNumber < oldNumber:
                continue

            # Get longest sub-path from cache (deep copy)
            if i in cache:
# TODO deep vs. shallow
#                pathObj = CacheEntry( path=cache[i].path.slice(), chars=cache[i].chars )
                pathObj = CacheEntry( path=copy.deepcopy(cache[i].path), chars=cache[i].chars )
            # Get longest sub-path by recursion
            else:
                pathObj = self.findMaxPath( i, groupEnd, cache )

            # Select longest sub-path
            if pathObj.chars > maxChars:
                maxChars = pathObj.chars
                returnObj = pathObj

        # Add current start to path
        returnObj.path.insert( 0, start )
        returnObj.chars += groups[start].chars

        # Save path to cache (deep copy)
        if start not in cache:
# TODO deep vs. shallow
#            cache.append( CacheEntry( path=returnObj.path.slice(), chars=returnObj.chars ) )
            cache[start] = CacheEntry( path=copy.deepcopy(returnObj.path), chars=returnObj.chars )

        return returnObj


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

        blocks = self.blocks
        groups = self.groups

        # Cycle through groups
        unlinked = False
        for group in range(len(groups)):
            blockStart = groups[group].blockStart
            blockEnd = groups[group].blockEnd

            # Unlink whole group if no block is at least blockMinLength words long and unique
            if groups[group].maxWords < self.config.blockMinLength and groups[group].unique is False:
                for block in range(blockStart, blockEnd + 1):
                    if blocks[block].type == '=':
                        self.unlinkSingleBlock( blocks[block] )
                        unlinked = True

            # Otherwise unlink block flanks
            else:
                # Unlink blocks from start
                for block in range(blockStart, blockEnd + 1):
                    if blocks[block].type == '=':
                        # Stop unlinking if more than one word or a unique word
                        if blocks[block].words > 1 or blocks[block].unique is True:
                            break
                        self.unlinkSingleBlock( blocks[block] )
                        unlinked = True
                        blockStart = block

                # Unlink blocks from end
                for block in range(blockEnd, blockStart, -1):
                    if blocks[block].type == '=':
                        # Stop unlinking if more than one word or a unique word
                        if (
                                blocks[block].words > 1 or
                                ( blocks[block].words == 1 and blocks[block].unique is True )
                                ):
                            break
                        self.unlinkSingleBlock( blocks[block] )
                        unlinked = True

        return unlinked


    ##
    ## Unlink text tokens of single block, convert them into into insertion/deletion ('+'/'-') pairs.
    ##
    ## @param[in] array blocks Blocks table object
    ## @param[out] WikEdDiffText newText, oldText Text objects, link property
    ##
    def unlinkSingleBlock( self, block ):

        # Cycle through old text
        j = block.oldStart
        for count in range(block.count):
            # Unlink tokens
            self.newText.tokens[ self.oldText.tokens[j].link ].link = None
            self.oldText.tokens[j].link = None
            j = self.oldText.tokens[j].next


    ##
    ## Collect deletion ('-') blocks from old text.
    ##
    ## @param[in] WikEdDiffText oldText Old Text object
    ## @param[out] array blocks Blocks table object
    ##
    def getDelBlocks(self):

        if self.config.timer is True:
            self.time( 'getDelBlocks' )

        blocks = self.blocks

        # Cycle through old text to find connected (linked, matched) blocks
        j = self.oldText.first
        i = None
        while j is not None:
            # Collect '-' blocks
            oldStart = j
            count = 0
            text = ''
            while j is not None and self.oldText.tokens[j].link is None:
                count += 1
                text += self.oldText.tokens[j].token
                j = self.oldText.tokens[j].next

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
                    ) )

            # Skip '=' blocks
            if j is not None:
                i = self.oldText.tokens[j].link
                while i is not None and j is not None and self.oldText.tokens[j].link == i:
                    i = self.newText.tokens[i].next
                    j = self.oldText.tokens[j].next

        if self.config.timer is True:
            self.timeEnd( 'getDelBlocks' )


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
            self.time( 'positionDelBlocks' )

        blocks = self.blocks
        groups = self.groups

        # Sort shallow copy of blocks by oldNumber
        blocksOld = sorted(blocks, key=lambda block: block.oldNumber)

        # Cycle through blocks in old text order
        for block in range(len(blocksOld)):
            delBlock = blocksOld[block]

            # '-' block only
            if delBlock.type != '-':
                continue

            # Find fixed '=' reference block from original block position to position '-' block
            # Similar to position marks '|' code

            # Get old text prev block
            prevBlockNumber = 0
            prevBlock = 0
            if block > 0:
                prevBlockNumber = blocksOld[block - 1].newBlock
                prevBlock = blocks[prevBlockNumber]

            # Get old text next block
            nextBlockNumber = 0
            nextBlock = 0
            if block < len(blocksOld) - 1:
                nextBlockNumber = blocksOld[block + 1].newBlock
                nextBlock = blocks[nextBlockNumber]

            # Move after prev block if fixed
            refBlock = 0
            if prevBlock != 0 and prevBlock.type == '=' and prevBlock.fixed is True:
                refBlock = prevBlock

            # Move before next block if fixed
            elif nextBlock != 0 and nextBlock.type == '=' and nextBlock.fixed is True:
                refBlock = nextBlock

            # Move after prev block if not start of group
            elif (
                    prevBlock != 0 and
                    prevBlock.type == '=' and
                    prevBlockNumber != groups[ prevBlock.group ].blockEnd
                    ):
                refBlock = prevBlock

            # Move before next block if not start of group
            elif (
                    nextBlock != 0 and
                    nextBlock.type == '=' and
                    nextBlockNumber != groups[ nextBlock.group ].blockStart
                    ):
                refBlock = nextBlock

            # Move after closest previous fixed block
            else:
                for fixed in range(block, -1, -1):
                    if blocksOld[fixed].type == '=' and blocksOld[fixed].fixed is True:
                        refBlock = blocksOld[fixed]
                        break

            # Move before first block
            if refBlock == 0:
                delBlock.newNumber =  -1

            # Update '-' block data
            else:
                delBlock.newNumber = refBlock.newNumber
                delBlock.section = refBlock.section
                delBlock.group = refBlock.group
                delBlock.fixed = refBlock.fixed

        # Sort '-' blocks in and update groups
        self.sortBlocks()

        if self.config.timer is True:
            self.timeEnd( 'positionDelBlocks' )


    ##
    ## Collect insertion ('+') blocks from new text.
    ##
    ## @param[in] WikEdDiffText newText New Text object
    ## @param[out] array blocks Blocks table object
    ##
    def getInsBlocks(self):

        if self.config.timer is True:
            self.time( 'getInsBlocks' )

        blocks = self.blocks

        # Cycle through new text to find insertion blocks
        i = self.newText.first
        while i is not None:

            # Jump over linked (matched) block
            while i is not None and self.newText.tokens[i].link is not None:
                i = self.newText.tokens[i].next

            # Detect insertion blocks ('+')
            if i is not None:
                iStart = i
                count = 0
                text = ''
                while i is not None and self.newText.tokens[i].link is None:
                    count += 1
                    text += self.newText.tokens[i].token
                    i = self.newText.tokens[i].next

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
                ) )

        # Sort '+' blocks in and update groups
        self.sortBlocks()

        if self.config.timer is True:
            self.timeEnd( 'getInsBlocks' )


    ##
    ## Sort blocks by new text token number and update groups.
    ##
    ## @param[in/out] array groups Groups table object
    ## @param[in/out] array blocks Blocks table object
    ##
    def sortBlocks(self):

        blocks = self.blocks
        groups = self.groups

        # Sort by newNumber, then by old number
        blocks.sort(key=lambda block: (int_or_null(block.newNumber), int_or_null(block.oldNumber)))

        # Cycle through blocks and update groups with new block numbers
        group = 0
        for block in range(len(blocks)):
            blockGroup = blocks[block].group
            if blockGroup is not None and blockGroup < len(groups):
                if blockGroup != group:
                    group = blocks[block].group
                    groups[group].blockStart = block
                    groups[group].oldNumber = blocks[block].oldNumber
                groups[blockGroup].blockEnd = block


    ##
    ## Set group numbers of insertion '+' blocks.
    ##
    ## @param[in/out] array groups Groups table object
    ## @param[in/out] array blocks Blocks table object, fixed and group properties
    ##
    def setInsGroups(self):

        if self.config.timer is True:
            self.time( 'setInsGroups' )

        blocks = self.blocks
        groups = self.groups

        # Set group numbers of '+' blocks inside existing groups
        for group in range(len(groups)):
            fixed = groups[group].fixed
            for block in range(groups[group].blockStart, groups[group].blockEnd + 1):
                if blocks[block].group is None:
                    blocks[block].group = group
                    blocks[block].fixed = fixed

        # Add remaining '+' blocks to new groups

        # Cycle through blocks
        for block in range(len(blocks)):
            # Skip existing groups
            if blocks[block].group is None:
                blocks[block].group = len(groups)

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
                ) )

        if self.config.timer is True:
            self.timeEnd( 'setInsGroups' )


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
            self.time( 'insertMarks' )

        blocks = self.blocks
        groups = self.groups
        moved = []
        color = 1

        # Make shallow copy of blocks
        blocksOld = blocks[:]

        # Enumerate copy
        for i, block in enumerate(blocksOld):
            block.number = i

        # Sort copy by oldNumber, then by newNumber
        blocksOld.sort(key=lambda block: (int_or_null(block.oldNumber), int_or_null(block.newNumber)))

        # Create lookup table: original to sorted
        lookupSorted = {}
        for i in range(len(blocksOld)):
            lookupSorted[ blocksOld[i].number ] = i

        # Cycle through groups (moved group)
        for moved in range(len(groups)):
            movedGroup = groups[moved]
            # NOTE: In JavaScript original there were 3 possible values for .fixed:
            #       true, false and null and only .fixed==false entries were processed
            #       in this loop. I think that the fixed==null entries correspond to
            #       those with .oldNumber==None.
            if movedGroup.fixed is True or movedGroup.oldNumber is None:
                continue
            movedOldNumber = movedGroup.oldNumber

            # Find fixed '=' reference block from original block position to position '|' block
            # Similar to position deletions '-' code

            # Get old text prev block
            prevBlock = None
            block = lookupSorted[ movedGroup.blockStart ]
            if block > 0:
                prevBlock = blocksOld[block - 1]

            # Get old text next block
            nextBlock = None
            block = lookupSorted[ movedGroup.blockEnd ]
            if block < len(blocksOld) - 1:
                nextBlock = blocksOld[block + 1]

            # Move after prev block if fixed
            refBlock = None
            if prevBlock is not None and prevBlock.type == '=' and prevBlock.fixed is True:
                refBlock = prevBlock

            # Move before next block if fixed
            elif nextBlock is not None and nextBlock.type == '=' and nextBlock.fixed is True:
                refBlock = nextBlock

            # Find closest fixed block to the left
            else:
                for fixed in range(lookupSorted[ movedGroup.blockStart ] - 1, -1, -1):
                    if blocksOld[fixed].type == '=' and blocksOld[fixed].fixed is True:
                        refBlock = blocksOld[fixed]
                        break

            # Get position of new mark block

            # No smaller fixed block, moved right from before first block
            if refBlock is None:
                newNumber = -1
                markGroup = len(groups)

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
                ) )
            else:
                newNumber = refBlock.newNumber
                markGroup = refBlock.group

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
            ) )

            # Set group color
            movedGroup.color = color
            movedGroup.movedFrom = markGroup
            color += 1

        # Sort '|' blocks in and update groups
        self.sortBlocks()

        if self.config.timer is True:
            self.timeEnd( 'insertMarks' )


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
    ## @return array Fragments array, abstraction layer for diff code
    ##
    def getDiffFragments(self):

        blocks = self.blocks
        groups = self.groups
        fragments = []

        # Make shallow copy of groups and sort by blockStart
        groupsSort = sorted(groups, key=lambda group: group.blockStart)

        # Cycle through groups
        for group in range(len(groupsSort)):
            blockStart = groupsSort[group].blockStart
            blockEnd = groupsSort[group].blockEnd

            # Add moved block start
            color = groupsSort[group].color
            if color != 0:
                if groupsSort[group].movedFrom < blocks[ blockStart ].group:
                    type = '(<'
                else:
                    type = '(>'
                fragments.append( Fragment(
                        text  = '',
                        type  = type,
                        color = color
                ) )

            # Cycle through blocks
            for block in range(blockStart, blockEnd + 1):
                type = blocks[block].type

                # Add '=' unchanged text and moved block
                if type == '=' or type == '-' or type == '+':
                    fragments.append( Fragment(
                            text  = blocks[block].text,
                            type  = type,
                            color = color
                    ) )

                # Add '<' and '>' marks
                elif type == '|':
                    movedGroup = groups[ blocks[block].moved ]

                    # Get mark text
                    markText = ''
                    for movedBlock in range(movedGroup.blockStart, movedGroup.blockEnd + 1):
                        if blocks[movedBlock].type == '=' or blocks[movedBlock].type == '-':
                            markText += blocks[movedBlock].text

                    # Get mark direction
                    if movedGroup.blockStart < blockStart:
                        markType = '<'
                    else:
                        markType = '>'

                    # Add mark
                    fragments.append( Fragment(
                            text  = markText,
                            type  = markType,
                            color = movedGroup.color
                    ) )

            # Add moved block end
            if color != 0:
                fragments.append( Fragment(
                        text  = '',
                        type  = ' )',
                        color = color
                ) )

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
                fragments[fragment - 1].text += fragments[fragment].text
                fragments.pop(fragment)
                fragment -= 1
            fragment += 1

        # Enclose in containers
        fragments.insert( 0, Fragment( text='', type='{', color=0 ) )
        fragments.insert( 1, Fragment( text='', type='[', color=0 ) )
        fragments.append(    Fragment( text='', type=']', color=0 ) )
        fragments.append(    Fragment( text='', type='}', color=0 ) )

        return fragments


    ##
    ## Clip unchanged sections from unmoved block text.
    ## Adds the following fagment types:
    ##   '~', ' ~', '~ ' omission indicators
    ##   '[', ']', ','   fragment start and end, fragment separator
    ##
    ## @param[in/out] array fragments Fragments array, abstraction layer for diff code
    ##
    def clipDiffFragments( self, fragments ):

        # Skip if only one fragment in containers, no change
        if len(fragments) == 5:
            return

        # Min length for clipping right
        minRight = self.config.clipHeadingRight
        if self.config.clipParagraphRightMin < minRight:
            minRight = self.config.clipParagraphRightMin
        if self.config.clipLineRightMin < minRight:
            minRight = self.config.clipLineRightMin
        if self.config.clipBlankRightMin < minRight:
            minRight = self.config.clipBlankRightMin
        if self.config.clipCharsRight < minRight:
            minRight = self.config.clipCharsRight

        # Min length for clipping left
        minLeft = self.config.clipHeadingLeft
        if self.config.clipParagraphLeftMin < minLeft:
            minLeft = self.config.clipParagraphLeftMin
        if self.config.clipLineLeftMin < minLeft:
            minLeft = self.config.clipLineLeftMin
        if self.config.clipBlankLeftMin < minLeft:
            minLeft = self.config.clipBlankLeftMin
        if self.config.clipCharsLeft < minLeft:
            minLeft = self.config.clipCharsLeft

        # Cycle through fragments
        fragment = -1
        while fragment + 1 < len(fragments):
            fragment += 1

            # Skip if not an unmoved and unchanged block
            type = fragments[fragment].type
            color = fragments[fragment].color
            if type != '=' or color != 0:
                continue

            # Skip if too short for clipping
            text = fragments[fragment].text
            if len(text) < minRight and len(text) < minLeft:
                continue

            # Get line positions including start and end
            lines = []
            lastIndex = 0
            for regExpMatch in self.config.regExp.clipLine.finditer(text):
                lines.append( regExpMatch.start() )
                lastIndex = regExpMatch.end()
            if lines[0] != 0:
                lines.insert( 0, 0 )
            if lastIndex != len(text):
                lines.append(len(text))

            # Get heading positions
            headings = []
            headingsEnd = []
            for regExpMatch in self.config.regExp.clipHeading.finditer(text):
                headings.append( regExpMatch.start() )
                headingsEnd.append( regExpMatch.end() )

            # Get paragraph positions including start and end
            paragraphs = []
            lastIndex = 0
            for regExpMatch in self.config.regExp.clipParagraph.finditer(text):
                paragraphs.append( regExpMatch.start() )
                lastIndex = regExpMatch.end()
            if len(paragraphs) == 0 or paragraphs[0] != 0:
                paragraphs.insert( 0, 0 )
            if lastIndex != len(text):
                paragraphs.append( len(text) )

            # Determine ranges to keep on left and right side
            rangeRight = None
            rangeLeft = None
            rangeRightType = ''
            rangeLeftType = ''

            # Find clip pos from left, skip for first non-container block
            if fragment != 2:
                # Maximum lines to search from left
                rangeLeftMax = len(text)
                if self.config.clipLinesLeftMax < len(lines):
                    rangeLeftMax = lines[self.config.clipLinesLeftMax]

                # Find first heading from left
                if rangeLeft is None:
                    for j in range(len(headingsEnd)):
                        if headingsEnd[j] > self.config.clipHeadingLeft or headingsEnd[j] > rangeLeftMax:
                            break
                        rangeLeft = headingsEnd[j]
                        rangeLeftType = 'heading'
                        break

                # Find first paragraph from left
                if rangeLeft is None:
                    for j in range(len(paragraphs)):
                        if (
                                paragraphs[j] > self.config.clipParagraphLeftMax or
                                paragraphs[j] > rangeLeftMax
                                ):
                            break
                        if paragraphs[j] > self.config.clipParagraphLeftMin:
                            rangeLeft = paragraphs[j]
                            rangeLeftType = 'paragraph'
                            break

                # Find first line break from left
                if rangeLeft is None:
                    for j in range(len(lines)):
                        if lines[j] > self.config.clipLineLeftMax or lines[j] > rangeLeftMax:
                            break
                        if lines[j] > self.config.clipLineLeftMin:
                            rangeLeft = lines[j]
                            rangeLeftType = 'line'
                            break

                # Find first blank from left
                if rangeLeft is None:
                    regExpMatch = self.config.regExp.clipBlank.search(text, pos=self.config.clipBlankLeftMin)
                    if regExpMatch:
                        if (
                                regExpMatch.start() < self.config.clipBlankLeftMax and
                                regExpMatch.start() < rangeLeftMax
                                ):
                            rangeLeft = regExpMatch.start()
                            rangeLeftType = 'blank'

                # Fixed number of chars from left
                if rangeLeft is None:
                    if self.config.clipCharsLeft < rangeLeftMax:
                        rangeLeft = self.config.clipCharsLeft
                        rangeLeftType = 'chars'

                # Fixed number of lines from left
                if rangeLeft is None:
                    rangeLeft = rangeLeftMax
                    rangeLeftType = 'fixed'

            # Find clip pos from right, skip for last non-container block
            if fragment != len(fragments) - 3:
                # Maximum lines to search from right
                rangeRightMin = 0
                if len(lines) >= self.config.clipLinesRightMax:
                    rangeRightMin = lines[len(lines) - self.config.clipLinesRightMax]

                # Find last heading from right
                if rangeRight is None:
                    for j in range(len(headings) - 1, -1, -1):
                        if (
                                headings[j] < len(text) - self.config.clipHeadingRight or
                                headings[j] < rangeRightMin
                                ):
                            break
                        rangeRight = headings[j]
                        rangeRightType = 'heading'
                        break

                # Find last paragraph from right
                if rangeRight is None:
                    for j in range(len(paragraphs) - 1, -1, -1):
                        if (
                                paragraphs[j] < len(text) - self.config.clipParagraphRightMax or
                                paragraphs[j] < rangeRightMin
                                ):
                            break
                        if paragraphs[j] < len(text) - self.config.clipParagraphRightMin:
                            rangeRight = paragraphs[j]
                            rangeRightType = 'paragraph'
                            break

                # Find last line break from right
                if rangeRight is None:
                    for j in range(len(lines) - 1, -1, -1):
                        if (
                                lines[j] < len(text) - self.config.clipLineRightMax or
                                lines[j] < rangeRightMin
                                ):
                            break
                        if lines[j] < len(text) - self.config.clipLineRightMin:
                            rangeRight = lines[j]
                            rangeRightType = 'line'
                            break

                # Find last blank from right
                if rangeRight is None:
                    startPos = len(text) - self.config.clipBlankRightMax
                    if startPos < rangeRightMin:
                        startPos = rangeRightMin
                    lastPos = None
                    regExpMatches = self.config.regExp.clipBlank.finditer(text, pos=startPos)
                    for regExpMatch in regExpMatches:
                        if regExpMatch.start() > len(text) - self.config.clipBlankRightMin:
                            if lastPos is not None:
                                rangeRight = lastPos
                                rangeRightType = 'blank'
                            break
                        lastPos = regExpMatch.start()

                # Fixed number of chars from right
                if rangeRight is None:
                    if len(text) - self.config.clipCharsRight > rangeRightMin:
                        rangeRight = len(text) - self.config.clipCharsRight
                        rangeRightType = 'chars'

                # Fixed number of lines from right
                if rangeRight is None:
                    rangeRight = rangeRightMin
                    rangeRightType = 'fixed'

            # Check if we skip clipping if ranges are close together
            if rangeLeft is not None and rangeRight is not None:
                # Skip if overlapping ranges
                if rangeLeft > rangeRight:
                    continue

                # Skip if chars too close
                skipChars = rangeRight - rangeLeft
                if skipChars < self.config.clipSkipChars:
                    continue

                # Skip if lines too close
                skipLines = 0
                for j in range(len(lines)):
                    if lines[j] > rangeRight or skipLines > self.config.clipSkipLines:
                        break
                    if lines[j] > rangeLeft:
                        skipLines += 1
                if skipLines < self.config.clipSkipLines:
                    continue

            # Skip if nothing to clip
            if rangeLeft is None and rangeRight is None:
                continue

            # Split left text
            textLeft = None
            omittedLeft = None
            if rangeLeft is not None:
                textLeft = text[ :rangeLeft ]

                # Remove trailing empty lines
                textLeft = self.config.regExp.clipTrimNewLinesLeft.sub( "", textLeft )

                # Get omission indicators, remove trailing blanks
                if rangeLeftType == 'chars':
                    omittedLeft = '~'
                    textLeft = self.config.regExp.clipTrimBlanksLeft.sub( "", textLeft )
                elif rangeLeftType == 'blank':
                    omittedLeft = ' ~'
                    textLeft = self.config.regExp.clipTrimBlanksLeft.sub( "", textLeft )

            # Split right text
            textRight = None
            omittedRight = None
            if rangeRight is not None:
                textRight = text[ rangeRight: ]

                # Remove leading empty lines
                textRight = self.config.regExp.clipTrimNewLinesRight.sub( "", textRight )

                # Get omission indicators, remove leading blanks
                if rangeRightType == 'chars':
                    omittedRight = '~'
                    textRight = self.config.regExp.clipTrimBlanksRight.sub( "", textRight )
                elif rangeRightType == 'blank':
                    omittedRight = '~ '
                    textRight = self.config.regExp.clipTrimBlanksRight.sub( "", textRight )

            # Remove split element
            fragments.pop( fragment )

            # Add left text to fragments list
            if rangeLeft is not None:
                fragments.insert( fragment, Fragment( text=textLeft, type='=', color=0 ) )
                fragment += 1
                if omittedLeft is not None:
                    fragments.insert( fragment, Fragment( text='', type=omittedLeft, color=0 ) )
                    fragment += 1

            # Add fragment container and separator to list
            if rangeLeft is not None and rangeRight is not None:
                fragments.insert( fragment, Fragment( text='', type=']', color=0 ) )
                fragment += 1
                fragments.insert( fragment, Fragment( text='', type=',', color=0 ) )
                fragment += 1
                fragments.insert( fragment, Fragment( text='', type='[', color=0 ) )
                fragment += 1

            # Add right text to fragments list
            if rangeRight is not None:
                if omittedRight is not None:
                    fragments.insert( fragment, Fragment( text='', type=omittedRight, color=0 ) )
                    fragment += 1
                fragments.insert( fragment, Fragment( text=textRight, type='=', color=0 ) )
                fragment += 1


    ##
    ## Count real words in text.
    ##
    ## @param string text Text for word counting
    ## @return int Number of words in text
    ##
    def wordCount( self, text ):

        return len(self.config.regExp.countWords.findall(text))


    ##
    ## Dummy plain text formatter used only for unit tests.
    ##
    ## @param array fragments Fragments array, abstraction layer for diff code
    ## @param string version
    ##   Output version: 'new' or 'old': only text from new or old version
    ## @return string Plain text representation of the diff for given version.
    ##
    def getDiffPlainText( self, fragments, version ):

        if version not in ['old', 'new']:
            raise Exception("version has to be either 'old' or 'new'")

        # Cycle through fragments
        output = ""
        for fragment in fragments:
            text = fragment.text
            type = fragment.type
            color = fragment.color

            # Add '=' (unchanged) text and moved block
            if type == '=':
                if color != 0:
                    if version != 'old':
                        output += text
                else:
                    output += text

            # Add '-' text
            elif type == '-' and version == 'old':
                # For old version skip '-' inside moved group
                if version == 'new' or color == 0:
                    output += text

            # Add '+' text
            elif type == '+' and version == 'new':
                output += text

            # Add '<' and '>' code
            elif type == '<' or type == '>':
                if version == 'old':
                    # Display as deletion at original position
                    output += text

        return output


    ##
    ## Test diff code for consistency with input versions.
    ## Prints results to debug console.
    ##
    ## @param WikEdDiffText oldText, newText Text objects
    ## @param array fragments Fragments array, abstraction layer for diff code
    ##
    def unitTests( self, oldText, newText, fragments ):

        # Check if output is consistent with new text
        diff = self.getDiffPlainText( fragments, 'new' )
        if diff != newText.text:
            logger.error(
                    'Error: wikEdDiff unit test failure: diff not consistent with new text version!'
            )
            self.error = False
            logger.debug( 'new text:\n' + text )
            logger.debug( 'new diff:\n' + diff )
        else:
            logger.debug( 'OK: wikEdDiff unit test passed: diff consistent with new text.' )

        # Check if output is consistent with old text
        diff = self.getDiffPlainText( fragments, 'old' )
        if diff != oldText.text:
            logger.error(
                    'Error: wikEdDiff unit test failure: diff not consistent with old text version!'
            )
            self.error = False
            logger.debug( 'old text:\n' + text )
            logger.debug( 'old diff:\n' + diff )
        else:
            logger.debug( 'OK: wikEdDiff unit test passed: diff consistent with old text.' )

    ##
    ## Dump blocks object to logger.
    ##
    ## @param string name Block name
    ## @param[in] array blocks Blocks table object
    ##
    def debugBlocks( self, name, blocks=None ):

        if blocks is None:
            blocks = self.blocks
        dump = "\n" + "\t".join(["i", "oldBl", "newBl", "oldNm", "newNm", "oldSt", "count", "uniq", "words", "chars", "type", "sect", "group", "fixed", "moved", "text"]) + "\n"
        for i, block in enumerate(blocks):
            dump += "\t".join(map(str, [i, block.oldBlock, block.newBlock,
                    block.oldNumber, block.newNumber, block.oldStart,
                    block.count, block.unique, block.words,
                    block.chars, block.type, block.section,
                    block.group, block.fixed, block.moved,
                    self.debugShortenText( block.text )])) + "\n"
        logger.debug( name + ':\n' + dump )


    ##
    ## Dump groups object to logger.
    ##
    ## @param string name Group name
    ## @param[in] array groups Groups table object
    ##
    def debugGroups( self, name, groups=None ):

        if groups is None:
            groups = self.groups
        dump = "\n" + "\t".join(["i", "oldNm", "blSta", "blEnd", "uniq", "maxWo", "words", "chars", "fixed", "oldNm", "mFrom", "color"]) + "\n"
        for i, group in enumerate(groups):
            dump += "\t".join(map(str, [i, group.oldNumber, group.blockStart,
                    group.blockEnd, group.unique, group.maxWords,
                    group.words, group.chars, group.fixed,
                    group.oldNumber, group.movedFrom, group.color])) + "\n"
        logger.debug( name + ':\n' + dump )


    ##
    ## Dump fragments array to logger.
    ##
    ## @param string name Fragments name
    ## @param array fragments Fragments array
    ##
    def debugFragments( self, name, fragments ):

        dump = "\n" + "\t".join(["i", "type", "color", "text"]) + "\n"
        for i, fragment in enumerate(fragments):
            dump += "\t".join(map(str, [i, fragment.type, fragment.color,
                    self.debugShortenText( fragment.text, 120, 40 )])) + "\n"
        logger.debug( name + ':\n' + dump )


    ##
    ## Dump borders array to logger.
    ##
    ## @param string name Arrays name
    ## @param[in] array border Match border array
    ##
    def debugBorders( self, name, borders ):

        dump = '\ni \t[ new \told ]\n'
        for i, border in enumerate(borders):
            dump += str(i) + ' \t[ ' + str(borders[i][0]) + ' \t' + str(borders[i][1]) + ' ]\n'
        logger.debug( name, dump )


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
        text = text.replace("\n", '\\n')
        text = text.replace("\t", '  ')
        if len(text) > max:
            text = text[ : max - 1 - end ] + '…' + text[ len(text) - end : ]
        return '"' + text + '"'


    ##
    ## Start timer 'label', analogous to JavaScript console timer.
    ## Usage: self.time( 'label' )
    ##
    ## @param string label Timer label
    ## @param[out] array timer Current time in milliseconds (float)
    ##
    def time( self, label ):

        self.timer[label] = time.time()


    ##
    ## Stop timer 'label', analogous to JavaScript console timer.
    ## Prints time in seconds since start to the logger.
    ## Usage: self.timeEnd( 'label' )
    ##
    ## @param string label Timer label
    ## @param bool noLog Do not log result
    ## @return float Time in milliseconds
    ##
    def timeEnd( self, label, noLog=False ):

        diff = 0
        if label in self.timer:
            start = self.timer[label]
            stop = time.time()
            diff = stop - start
            del self.timer[label]
            if noLog is not True:
                logger.debug( "{}: {:.2g} s".format(label, diff) )
        return diff


    ##
    ## Print recursion timer results to logger.
    ## Usage: self.timeRecursionEnd()
    ##
    ## @param string text Text label for output
    ## @param[in] array recursionTimer Accumulated recursion times
    ##
    def timeRecursionEnd( self, text ):

        if len(self.recursionTimer) > 1:
            # TODO: WTF? (they are accumulated first..)
            # Subtract times spent in deeper recursions
            timerEnd = len(self.recursionTimer) - 1
            for i in range(timerEnd):
                self.recursionTimer[i] -= self.recursionTimer[i + 1]

            # Log recursion times
            for i in range(len(self.recursionTimer)):
                logger.debug( "{} recursion {}: {:.2g} s".format(text, i, self.recursionTimer[i]) )

        self.recursionTimer.clear()


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
        self.parent = parent

        # @var string text Text of this version
        self.text = str(text)

        # @var array tokens Tokens list
        self.tokens = []

        # @var int first, last First and last index of tokens list
        self.first = None
        self.last = None

        # @var array words Word counts for version text
        self.words = {}


        # Parse and count words and chunks for identification of unique real words
        if self.parent.config.timer is True:
            self.parent.time( 'wordParse' )
        self.wordParse( self.parent.config.regExp.countWords )
        self.wordParse( self.parent.config.regExp.countChunks )
        if self.parent.config.timer is True:
            self.parent.timeEnd( 'wordParse' )


    ##
    ## Parse and count words and chunks for identification of unique words.
    ##
    ## @param string regExp Regular expression for counting words
    ## @param[in] string text Text of version
    ## @param[out] array words Number of word occurrences
    ##
    def wordParse( self, regExp ):

        for regExpMatch in regExp.finditer(self.text):
            word = regExpMatch.group()
            self.words.setdefault(word, 0)
            self.words[word] += 1


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
        first = current

        # Split full text or specified token
        if token is None:
            prev = None
            next = None
            text = self.text
        else:
            prev = self.tokens[token].prev
            next = self.tokens[token].next
            text = self.tokens[token].token

        # Split text into tokens, regExp match as separator
        number = 0
        split = []
        lastIndex = 0
        regExp = self.parent.config.regExp.split[level]
        for regExpMatch in regExp.finditer(text):
            if regExpMatch.start() > lastIndex:
                split.append( text[lastIndex : regExpMatch.start()] )
            split.append(regExpMatch.group())
            lastIndex = regExpMatch.end()
        if lastIndex < len(text):
            split.append( text[ lastIndex: ] )

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
            number += 1

            # Link previous item to current
            if prev is not None:
                self.tokens[prev].next = current
            prev = current
            current += 1

        # Connect last new item and existing next item
        if number > 0 and token is not None:
            if prev is not None:
                self.tokens[prev].next = next
            if next is not None:
                self.tokens[next].prev = prev

        # Set text first and last token index
        if number > 0:
            # Initial text split
            if token is None:
                self.first = 0
                self.last = prev

            # First or last token has been split
            else:
                if token == self.first:
                    self.first = first
                if token == self.last:
                    self.last = prev


    ##
    ## Split unique unmatched tokens into smaller tokens.
    ##
    ## @param string level Level of splitting: line, sentence, chunk, or word
    ## @param[in] array tokens Tokens list
    ##
    def splitRefine( self, regExp ):

        # Cycle through tokens list
        i = self.first
        while i is not None:
            # Refine unique unmatched tokens into smaller tokens
            if self.tokens[i].link is None:
                self.splitText( regExp, i )
            i = self.tokens[i].next


    ##
    ## Enumerate text token list before detecting blocks.
    ##
    ## @param[out] array tokens Tokens list
    ##
    def enumerateTokens(self):

        # Enumerate tokens list
        number = 0
        i = self.first
        while i is not None:
            self.tokens[i].number = number
            number += 1
            i = self.tokens[i].next


    ##
    ## Dump tokens object to logger.
    ##
    ## @param string name Text name
    ## @param[in] int first, last First and last index of tokens list
    ## @param[in] array tokens Tokens list
    ##
    def debugText( self, name ):

        tokens = self.tokens
        dump = 'first: ' + str(self.first) + '\tlast: ' + str(self.last) + '\n'
        dump += '\ni \tlink \t(prev \tnext) \tuniq \t#num \t"token"\n'
        i = self.first
        while i is not None:
            dump += "{} \t{} \t({} \t{}) \t{} \t#{} \t{}\n".format(i, tokens[i].link, tokens[i].prev, tokens[i].next,
                                                                   tokens[i].unique, tokens[i].number,
                                                                   self.parent.debugShortenText( tokens[i].token ))
            i = tokens[i].next
        logger.debug( name + ':\n' + dump )
