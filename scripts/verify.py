"""Check every page's glyph multiset equals the converted source; report remaining traditional chars.

usage: verify.py source.pdf converted.pdf
"""
import collections
import os
import sys

import fitz
import opencc

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from convert import convert_chars  # noqa: E402

t2s = opencc.OpenCC("t2s")


def check(src_path, dst_path):
    src, dst = fitz.open(src_path), fitz.open(dst_path)
    lines, bad = [], 0
    for i, (a, b) in enumerate(zip(src, dst)):
        ta = convert_chars(list(a.get_text().replace("\n", "")))
        tb = b.get_text().replace("\n", "")
        ca = collections.Counter(c for c in ta if not c.isspace())
        cb = collections.Counter(c for c in tb if not c.isspace())
        if ca != cb:
            bad += 1
            lines.append("page %d lost: %s extra: %s" % (i + 1, dict(ca - cb), dict(cb - ca)))
        trad = {c for c in tb if t2s.convert(c) != c}
        if trad:
            lines.append("page %d still traditional: %s" % (i + 1, trad))
    lines.append("pages %d, mismatched %d" % (len(src), bad))
    return lines


if __name__ == "__main__":
    print("\n".join(check(sys.argv[1], sys.argv[2])))
