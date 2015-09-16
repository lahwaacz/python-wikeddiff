#! /usr/bin/env python3

import re

from .utils import dotdictify

__all__ = ["HtmlFormatter"]

class HtmlFormatter:

# TODO: check this
    # RegExp detecting blank-only and single-char blocks
    blankBlock = re.compile( "^([^\t\S]+|[^\t])$", re.MULTILINE )

    # Messages.
    msg = {
        'wiked-diff-empty': '(No difference)',
        'wiked-diff-same':  '=',
        'wiked-diff-ins':   '+',
        'wiked-diff-del':   '-',
        'wiked-diff-block-left':  '◀',
        'wiked-diff-block-right': '▶',
        'wiked-diff-block-left-nounicode':  '<',
        'wiked-diff-block-right-nounicode': '>',
        'wiked-diff-error': 'Error: diff not consistent with versions!'
    }

    # Template for standalone HTML page. This is not necessary in the JavaScript
    # version since the formatted diff is inserted directly into the page in the
    # browser.
    fullHtmlTemplate = """
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

    # CSS stylesheet. In the JavaScript version it is inserted directly into the
    # page in the browser.
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
    # Replace mark symbols
    stylesheet = stylesheet.replace("{cssMarkLeft}", cssMarkLeft) \
                           .replace("{cssMarkRight}", cssMarkRight)

    # JavaScript code providing additional functionality on the rendered HTML
    # page. In the JavaScript version it is inserted directly into the page in
    # the browser.
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
    ## Main formatter method which creates HTML formatted diff code from diff fragments.
    ##
    ## @param array fragments Fragments array, abstraction layer for diff code
    ## @param bool error Whether to add an error indicator to mark diff as inconsistent (False)
    ## @param bool showBlockMoves
    ##   Enable block move layout with highlighted blocks and marks at the original positions (True)
    ## @param bool coloredBlocks
    ##   Display blocks in differing colors (rainbow color scheme) (False)
    ## @param bool coloredBlocks
    ##   Do not use UniCode block move marks (legacy browsers) (False)
    ## @return string Html code of diff
    ##
    def getDiffHtml( self,
                     fragments,
                     error=False,
                     showBlockMoves=True,
                     coloredBlocks=False,
                     noUnicodeSymbols=False ):

        # No change, only one unchanged block in containers
        if len(fragments) == 5 and fragments[2].type == '=':
            return self.htmlCode.containerStart + \
                   self.htmlCode.noChangeStart + \
                   self.htmlEscape( self.msg['wiked-diff-empty'] ) + \
                   self.htmlCode.noChangeEnd + \
                   self.htmlCode.containerEnd

        # Cycle through fragments
        htmlFragments = []
        for fragment in fragments:
            text = fragment.text
            type = fragment.type
            color = fragment.color
            html = ''

            # Test if text is blanks-only or a single character
            blank = False
            if text != '':
                blank = self.blankBlock.search( text )

            # Add container start markup
            if type == '{':
                html = self.htmlCode.containerStart
            # Add container end markup
            elif type == '}':
                html = self.htmlCode.containerEnd

            # Add fragment start markup
            if type == '[':
                html = self.htmlCode.fragmentStart
            # Add fragment end markup
            elif type == ']':
                html = self.htmlCode.fragmentEnd
            # Add fragment separator markup
            elif type == ',':
                html = self.htmlCode.separator

            # Add omission markup
            if type == '~':
                html = self.htmlCode.omittedChars

            # Add omission markup
            if type == ' ~':
                html = ' ' + self.htmlCode.omittedChars

            # Add omission markup
            if type == '~ ':
                html = self.htmlCode.omittedChars + ' '
            # Add colored left-pointing block start markup
            elif type == '(<':
                # Get title
                if noUnicodeSymbols is True:
                    title = self.msg['wiked-diff-block-left-nounicode']
                else:
                    title = self.msg['wiked-diff-block-left']

                # Get html
                if coloredBlocks is True:
                    html = self.htmlCode.blockColoredStart
                else:
                    html = self.htmlCode.blockStart
                html = self.htmlCustomize( html, color, title, noUnicodeSymbols )

            # Add colored right-pointing block start markup
            elif type == '(>':
                # Get title
                if noUnicodeSymbols is True:
                    title = self.msg['wiked-diff-block-right-nounicode']
                else:
                    title = self.msg['wiked-diff-block-right']

                # Get html
                if coloredBlocks is True:
                    html = self.htmlCode.blockColoredStart
                else:
                    html = self.htmlCode.blockStart
                html = self.htmlCustomize( html, color, title, noUnicodeSymbols )

            # Add colored block end markup
            elif type == ' )':
                html = self.htmlCode.blockEnd

            # Add '=' (unchanged) text and moved block
            if type == '=':
                text = self.htmlEscape( text )
                if color != 0:
                    html = self.markupBlanks( text, True )
                else:
                    html = self.markupBlanks( text )

            # Add '-' text
            elif type == '-':
                text = self.htmlEscape( text )
                text = self.markupBlanks( text, True )
                if blank is True:
                    html = self.htmlCode.deleteStartBlank
                else:
                    html = self.htmlCode.deleteStart
                html += text + self.htmlCode.deleteEnd

            # Add '+' text
            elif type == '+':
                text = self.htmlEscape( text )
                text = self.markupBlanks( text, True )
                if blank is True:
                    html = self.htmlCode.insertStartBlank
                else:
                    html = self.htmlCode.insertStart
                html += text + self.htmlCode.insertEnd

            # Add '<' and '>' code
            elif type == '<' or type == '>':
                # Display as deletion at original position
                if showBlockMoves is False:
                    text = self.htmlEscape( text )
                    text = self.markupBlanks( text, True )
                    if blank is True:
                        html = self.htmlCode.deleteStartBlank + \
                               text + \
                               self.htmlCode.deleteEnd
                    else:
                        html = self.htmlCode.deleteStart + text + self.htmlCode.deleteEnd

                # Display as mark
                else:
                    if type == '<':
                        if coloredBlocks is True:
                            html = self.htmlCustomize( self.htmlCode.markLeftColored, color, text, noUnicodeSymbols )
                        else:
                            html = self.htmlCustomize( self.htmlCode.markLeft, color, text, noUnicodeSymbols )
                    else:
                        if coloredBlocks is True:
                            html = self.htmlCustomize( self.htmlCode.markRightColored, color, text, noUnicodeSymbols )
                        else:
                            html = self.htmlCustomize( self.htmlCode.markRight, color, text, noUnicodeSymbols )

            htmlFragments.append( html )

        # Join fragments
        html = "".join(htmlFragments)

        # Add error indicator
        if error is True:
            html = self.htmlCode.errorStart + html + self.htmlCode.errorEnd

        return html


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
    def htmlCustomize( self, html, number, title=None, noUnicodeSymbols=False ):

        # Replace {number} with class/color/block/mark/id number
        html = html.replace("{number}", str(number))

        # Replace {nounicode} with wikEdDiffNoUnicode class name
        if noUnicodeSymbols is True:
            html = html.replace("{nounicode}", ' wikEdDiffNoUnicode')
        else:
            html = html.replace("{nounicode}", '')

        # Shorten title text, replace {title}
        if title != None:
            max = 512
            end = 128
            gapMark = ' [...] '
            if len(title) > max:
                title = title[ : max - len(gapMark) - end ] + \
                        gapMark + \
                        title[ len(title) - end : ]
            title = self.htmlEscape( title )
            title = title.replace("\t", '&nbsp;&nbsp;')
            title = title.replace("  ", '&nbsp;&nbsp;')
            html = html.replace("{title}", title)

        return html


    ##
    ## Replace html-sensitive characters in output text with character entities.
    ##
    ## @param string html Html code to be escaped
    ## @return string Escaped html code
    ##
    def htmlEscape( self, html ):

        html = html.replace("&", '&amp;')
        html = html.replace("<", '&lt;')
        html = html.replace(">", '&gt;')
        html = html.replace('"', '&quot;')
        return html


    ##
    ## Markup tabs, newlines, and spaces in diff fragment text.
    ##
    ## @param bool highlight Highlight newlines and spaces in addition to tabs
    ## @param string html Text code to be marked-up
    ## @return string Marked-up text
    ##
    def markupBlanks( self, html, highlight=False ):

        if highlight is True:
            html = html.replace(" ", self.htmlCode.space)
            html = html.replace("\n", self.htmlCode.newline)
        html = html.replace("\t", self.htmlCode.tab)
        return html
