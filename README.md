# Python-wikEdDiff

WikEdDiff is a visual inline-style difference engine with block move support.

The original wikEdDiff is an improved JavaScript diff library that returns
html/css-formatted new text version with highlighted deletions, insertions,
and block moves. It is also available as a MediaWiki extension, which is a
one-to-one synced port with changes and fixes applied to both versions.

 - JavaScript library (mirror): https://en.wikipedia.org/wiki/User:Cacycle/diff
 - JavaScript online tool: http://cacycle.altervista.org/wikEd-diff-tool.html
 - MediaWiki extension: https://www.mediawiki.org/wiki/Extension:wikEdDiff

**Python-wikEdDiff** is a port of the original JavaScript library to Python.
There were no changes to the algorithm, so all credits go to the original
author, [Cacycle](https://en.wikipedia.org/wiki/User:Cacycle).

## Features

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
 - Added an ANSI color formatter and a console demo script (`diff.py`).

## Installation

    pip install git+git://github.com/lahwaacz/python-wikeddiff.git

## License

The Python port (python-wikeddiff) is distributed under the terms of the
[GNU General Public License v3.0](http://www.gnu.org/copyleft/gpl.html)
(see LICENSE).
