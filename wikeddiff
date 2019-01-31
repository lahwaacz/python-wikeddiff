#! /usr/bin/env python3

import argparse
import logging

from WikEdDiff import *

def setTerminalLogging(level=logging.DEBUG):
    # create console handler and set level
    handler = logging.StreamHandler()

    # create formatter
    formatter = logging.Formatter("{levelname:8} {message}", style="{")
    handler.setFormatter(formatter)

    # add the handler to the root logger
    logger = logging.getLogger()
    logger.addHandler(handler)
    logger.setLevel(level)

    return logger

if __name__ == "__main__":

    argparser = argparse.ArgumentParser(description="Python-WikEdDiff demo utility", usage="%(prog)s [options] old_file new_file")

    def str2bool(v):
        return v.lower() in ["true", "yes", "1"]

    _diff = argparser.add_argument_group(title="diff options")
    _diff.add_argument("--full-diff", dest="fullDiff", type=str2bool,
            help="Show complete un-clipped diff text (default: %(default)s)")
    _diff.add_argument("--char-diff", dest="charDiff", type=str2bool,
            help="Enable character-refined diff (default: %(default)s)")
    _diff.add_argument("--repeated-diff", dest="repeatedDiff", type=str2bool,
            help="Enable repeated diff to resolve problematic sequences (default: %(default)s)")
    _diff.add_argument("--recursive-diff", dest="recursiveDiff", type=str2bool,
            help="Enable recursive diff to resolve problematic sequences (default: %(default)s)")
    _diff.add_argument("--recursion-max", dest="recursionMax", type=int,
            help="Maximum recursion depth (default: %(default)s)")
    _diff.add_argument("--unlink-blocks", dest="unlinkBlocks", type=str2bool,
            help="Reject blocks if they are too short and their words are not unique, " + \
                 "prevents fragmentated diffs for very different versions (default: %(default)s)")
    _diff.add_argument("--unlink-max", dest="unlinkMax", type=int,
            help="Maximum number of rejection cycles (default: %(default)s)")
    _diff.add_argument("--block-min-length", dest="blockMinLength", type=int,
            help="Reject blocks if shorter than this number of real words (default: %(default)s)")
    _diff.add_argument("--strip-trailing-newline", dest="stripTrailingNewline", type=str2bool,
            help="Strip trailing newline off of texts (default: %(default)s)")
    _diff.add_argument("--debug", dest="debug", type=str2bool,
            help="Show debug infos and stats (block, group, and fragment data) in debug console (default: %(default)s)")
    _diff.add_argument("--timer", dest="timer", type=str2bool,
            help="Show timing results in debug console (default: %(default)s)")
    _diff.add_argument("--unit-testing", dest="unitTesting", type=str2bool,
            help="Run unit tests to prove correct working, display results in debug console (default: %(default)s)")

    _diff_defaults = {
        'fullDiff'             : False,
        'charDiff'             : True,
        'repeatedDiff'         : True,
        'recursiveDiff'        : True,
        'recursionMax'         : 10,
        'unlinkBlocks'         : True,
        'unlinkMax'            : 5,
        'blockMinLength'       : 3,
        'stripTrailingNewline' : True,
        'debug'                : False,
        'timer'                : False,
        'unitTesting'          : False,
    }
    _diff.set_defaults(**_diff_defaults)

    _formatter = argparser.add_argument_group(title="formatter options")
    _formatter.add_argument("--formatter", choices=["html", "ansi"], default="ansi",
            help="Selects a formatter for diff output (default: %(default)s)")
    _formatter.add_argument("--show-block-moves", dest="showBlockMoves", type=str2bool, default=True,
            help="Enable block move layout with highlighted blocks and marks at the original positions (default: %(default)s)")
    _formatter.add_argument("--colored-blocks", dest="coloredBlocks", type=str2bool, default=True,
            help="Display blocks in differing colors (rainbow color scheme) (default: %(default)s")

    argparser.add_argument("old_file", type=argparse.FileType("r"),
            help="Path to the old revision file.")
    argparser.add_argument("new_file", type=argparse.FileType("r"),
            help="Path to the new revision file.")

    # Parse command line arguments
    args = argparser.parse_args()

    # Set terminal logging
    if args.debug or args.timer or args.unitTesting:
        setTerminalLogging()

    # Create config for WikEdDiff
    config = WikEdDiffConfig()
    _diff_args = dict( (k,v) for k,v in args.__dict__.items() if k in _diff_defaults )
    config.__dict__.update(_diff_args)

    # Get diff fragments
    wd = WikEdDiff(config)
    fragments = wd.diff(args.old_file.read(), args.new_file.read())

    if args.formatter == "html":
        # Create HTML formatted diff code from diff fragments
        formatter = HtmlFormatter()
        diff_html = formatter.format( fragments, showBlockMoves=args.showBlockMoves, coloredBlocks=args.coloredBlocks, error=wd.error )

        # Create standalone HTML page
        full_html = formatter.fullHtmlTemplate.format(title=args.new_file, script=formatter.javascript, stylesheet=formatter.stylesheet, diff=diff_html)

        print(full_html)
    else:
        formatter = AnsiFormatter()
        diff_ansi = formatter.format( fragments, showBlockMoves=args.showBlockMoves, coloredBlocks=args.coloredBlocks )
        print(diff_ansi)
