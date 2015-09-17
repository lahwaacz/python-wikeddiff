#! /usr/bin/env python3

import sys
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

    if len(sys.argv) != 3:
        print("usage: {} old_file new_file".format(sys.argv[0]))
        sys.exit(1)

    setTerminalLogging()

    f1 = open(sys.argv[1], "r")
    f2 = open(sys.argv[2], "r")

    config = WikEdDiffConfig()
    wd = WikEdDiff(config)
    fragments = wd.diff(f1.read(), f2.read())

    # Create HTML formatted diff code from diff fragments
    formatter = HtmlFormatter()
    diff_html = formatter.format( fragments, coloredBlocks=True, error=wd.error )

    # Create standalone HTML page
    full_html = formatter.fullHtmlTemplate.format(title=sys.argv[2], script=formatter.javascript, stylesheet=formatter.stylesheet, diff=diff_html)

    out = open("output.html", "w")
    out.write(full_html)
