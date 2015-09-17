#! /usr/bin/env python3

import re

__all__ = ["AnsiFormatter"]

class AnsiFormatter:

    # RegExp detecting blank-only and single-char blocks
    blankBlock = re.compile( "^([^\t\S]+|[^\t])$"  )

    # Messages
    msg = {
        'wiked-diff-empty': '(No difference)',
        'wiked-diff-same':  '=',
        'wiked-diff-ins':   '+',
        'wiked-diff-del':   '-',
        'wiked-diff-block-left':  '◀',
        'wiked-diff-block-right': '▶',
    }

    # Characters used for highlighting
#    newline = "\n"
#    tab = "\t"
#    space = " "
    newline = "¶\n"
    tab = "→"
    space = "·"
    omittedChars = "…"

    # Colors
    color_insert = 10
    color_delete = 9
    color_same = None
    color_separator = 5

    # Default color for moved blocks
    color_moved = 3

    # Block colors
    colors_fg = [226, 136, 214, 105, 165, 128, 14, 63, 133]
    colors_bg = colors_fg

    def __init__(self):
        # Stack of color codes
        self.color_stack = []

    ##
    ## Main formatter method which formats diff fragments using ANSI colors.
    ##
    ## @param array fragments Fragments array, abstraction layer for diff code
    ## @param bool showBlockMoves
    ##   Enable block move layout with highlighted blocks and marks at the original positions (True)
    ## @param bool coloredBlocks
    ##   Display blocks in differing colors (rainbow color scheme) (False)
    ## @return string ANSI formatted code of diff
    ##
    def format( self,
                fragments,
                showBlockMoves=True,
                coloredBlocks=False ):

        # No change, only one unchanged block in containers
        if len(fragments) == 5 and fragments[2].type == '=':
            return self.containerStart + \
                   self.noChangeStart + \
                   self.ansiEscape( self.msg['wiked-diff-empty'] ) + \
                   self.noChangeEnd + \
                   self.containerEnd

        # Cycle through fragments
        markupFragments = []
        for fragment in fragments:
            text = fragment.text
            type = fragment.type
            color = fragment.color
            markup = ""

            # Test if text is blanks-only or a single character
            blank = False
            if text != '':
                blank = self.blankBlock.search( text ) is not None

            # Add container start markup
            if type == '{':
                markup = self.containerStart
            # Add container end markup
            elif type == '}':
                markup = self.containerEnd

            # Add fragment start markup
            elif type == '[':
                markup = self.fragmentStart
            # Add fragment end markup
            elif type == ']':
                markup = self.fragmentEnd
            # Add fragment separator markup
            elif type == ',':
                markup = self.separator

            # Add omission markup
            elif type == '~':
                markup = self.omittedChars
            # Add omission markup
            elif type == ' ~':
                markup = ' ' + self.omittedChars

            # Add omission markup
            elif type == '~ ':
                markup = self.omittedChars + ' '
            # Add colored left-pointing block start markup
            elif type == '(<':
                if coloredBlocks is True:
                    markup = self.blockColoredStart(color)
                else:
                    markup = self.blockStart

            # Add colored right-pointing block start markup
            elif type == '(>':
                if coloredBlocks is True:
                    markup = self.blockColoredStart(color)
                else:
                    markup = self.blockStart

            # Add colored block end markup
            elif type == ' )':
                markup = self.blockEnd

            # Add '=' (unchanged) text and moved block
            elif type == '=':
                text = self.ansiEscape( text )
                if color != 0:
                    markup = self.markupBlanks( text, True )
                else:
                    markup = self.markupBlanks( text )

            # Add '-' text
            elif type == '-':
                text = self.ansiEscape( text )
                text = self.markupBlanks( text, True )
                if blank is True:
                    markup = self.deleteStartBlank
                else:
                    markup = self.deleteStart
                markup += text + self.deleteEnd

            # Add '+' text
            elif type == '+':
                text = self.ansiEscape( text )
                text = self.markupBlanks( text, True )
                if blank is True:
                    markup = self.insertStartBlank
                else:
                    markup = self.insertStart
                markup += text + self.insertEnd

            # Add '<' and '>' code
            elif type == '<' or type == '>':
                # Display as deletion at original position
                if showBlockMoves is False:
                    text = self.ansiEscape( text )
                    text = self.markupBlanks( text, True )
                    if blank is True:
                        markup = self.deleteStartBlank + \
                               text + \
                               self.deleteEnd
                    else:
                        markup = self.deleteStart + text + self.deleteEnd

                # Display as mark
                else:
                    if type == '<':
                        if coloredBlocks is True:
                            markup = self.markLeftColored(color)
                        else:
                            markup = self.markLeft
                    else:
                        if coloredBlocks is True:
                            markup = self.markRightColored(color)
                        else:
                            markup = self.markRight

            markupFragments.append( markup )

        # Join fragments
        markup = "".join(markupFragments)

        # Clear the color stack
        assert(len(self.color_stack) == 0)
#        self.color_stack.clear()

        return markup


    ##
    ## Markup tabs, newlines, and spaces in diff fragment text.
    ##
    ## @param bool highlight Highlight newlines and spaces in addition to tabs
    ## @param string text Text code to be marked-up
    ## @return string Marked-up text
    ##
    def markupBlanks( self, text, highlight=False ):

        if highlight is True:
            text = text.replace(" ", self.space)
            text = text.replace("\n", self.newline)
        text = text.replace("\t", self.tab)
        return text


    ##
    ## Replace ANSI escape codes with their plain-text representation.
    ##
    ## @param string text Text to be escaped
    ## @return string Escaped code
    ##
    def ansiEscape( self, text ):

        return text.replace("\033[", "\\033[")


    # Assemble ANSI escape code for given colors, add it to the stack and return it.
    def pushColor(self, fg=None, bg=None):
        code = "\033[00"
        if fg is not None:
            code += ";38;5;" + str(fg)
        if bg is not None:
            code += ";48;5;" + str(bg)
        code += "m"
        self.color_stack.append(code)
        return code

    # Pop current color from the stack and return the next one on the stack.
    def popColor(self):
        try:
            self.color_stack.pop()
            return self.color_stack[-1]
        except IndexError:
            # fall back to reset if the stack is empty
            return "\033[0m"

    @property
    def noChangeStart(self):
        return self.pushColor(self.color_same)
    @property
    def noChangeEnd(self):
        return self.popColor()

    @property
    def containerStart(self):
        return self.pushColor()
    @property
    def containerEnd(self):
        return self.popColor()

    @property
    def fragmentStart(self):
        return ""
    @property
    def fragmentEnd(self):
        return ""
    @property
    def separator(self):
        return self.pushColor(self.color_separator) + "\n@@@ --- @@@\n" + self.popColor()

    @property
    def insertStart(self):
        return self.pushColor(self.color_insert)
    @property
    def insertStartBlank(self):
        return self.pushColor(fg=0, bg=self.color_insert)
    @property
    def insertEnd(self):
        return self.popColor()

    @property
    def deleteStart(self):
        return self.pushColor(self.color_delete)
    @property
    def deleteStartBlank(self):
        return self.pushColor(fg=0, bg=self.color_delete)
    @property
    def deleteEnd(self):
        return self.popColor()

    @property
    def blockStart(self):
        return self.pushColor(fg=self.color_moved)
    def blockColoredStart(self, num):
        color = self.colors_fg[ num % len(self.colors_fg) ]
        return self.pushColor(fg=color)
    @property
    def blockEnd(self):
        return self.popColor()

    @property
    def markLeft(self):
        fg = 0
        bg = self.color_moved
        return self.pushColor(fg=fg, bg=bg) + self.msg["wiked-diff-block-left"] + self.popColor()
    def markLeftColored(self, num):
        fg = 0
        bg = self.colors_bg[ num % len(self.colors_bg) ]
        return self.pushColor(fg=fg, bg=bg) + self.msg["wiked-diff-block-left"] + self.popColor()

    @property
    def markRight(self):
        fg = 0
        bg = self.color_moved
        return self.pushColor(fg=fg, bg=bg) + self.msg["wiked-diff-block-right"] + self.popColor()
    def markRightColored(self, num):
        fg = 0
        bg = self.colors_bg[ num % len(self.colors_bg) ]
        return self.pushColor(fg=fg, bg=bg) + self.msg["wiked-diff-block-right"] + self.popColor()
