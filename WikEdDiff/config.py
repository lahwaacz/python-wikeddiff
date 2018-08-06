#! /usr/bin/env python3

import re

from .utils import dotdictify

__all__ = ["WikEdDiffConfig"]

##
## Configuration and customization settings.
##
## @class WikEdDiffConfig
##
class WikEdDiffConfig:
    # Core diff settings (with default values).

    ##
    ## @var bool config.fullDiff
    ##   Show complete un-clipped diff text (False)
    ##
    fullDiff = False

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
    ## @var bool config.stripTrailingNewline
    ##   Strip trailing newline off of texts (True)
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
    regExpLetters = 'a-zA-Z0-9' + re.sub("(\w{4})", r"\\u\g<1>",
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

    # Regular expressions.

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
