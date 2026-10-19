"""Convert several PDFs to Simplified Chinese in parallel, then verify each.

usage: batch.py OUTDIR file1.pdf [file2.pdf ...]
Output names are the input names converted to simplified, with （简体） appended.
"""
import os
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert  # noqa: E402
import verify  # noqa: E402


def out_name(src):
    stem = os.path.splitext(os.path.basename(src))[0]
    stem = convert.convert_chars(list(stem)).rstrip("_ ")
    return stem + "（简体）.pdf"


def job(src, outdir):
    dst = os.path.join(outdir, out_name(src))
    stats = convert.process(src, dst)
    report = verify.check(src, dst)
    return src, dst, stats, report


if __name__ == "__main__":
    outdir, files = sys.argv[1], sys.argv[2:]
    os.makedirs(outdir, exist_ok=True)
    with ProcessPoolExecutor(max_workers=min(len(files), os.cpu_count() or 4)) as ex:
        for src, dst, stats, report in ex.map(job, files, [outdir] * len(files)):
            missing = {k: v for k, v in stats.items() if k.startswith("missing:")}
            print("==", os.path.basename(src), "->", dst)
            print("   redrawn chars:", stats["chars"], "| missing glyphs:", missing or "none")
            for line in report:
                print("  ", line)
