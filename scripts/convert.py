"""Convert Traditional Chinese text in a PDF to Simplified Chinese, keeping layout.

Each line containing text that changes is removed (text only) and redrawn
character-by-character at the original glyph origins using Noto Sans SC.
"""
import collections
import os
import sys
import unicodedata

import fitz
import opencc

HERE = os.path.dirname(os.path.abspath(__file__))


def find_font(weight):
    """Fonts shipped with the skill, else the ones setup.sh downloaded."""
    name = "NotoSansSC-%s.otf" % weight
    cache = os.environ.get("PDF_T2S_HOME", os.path.expanduser("~/.cache/pdf-t2s"))
    for d in (os.path.join(HERE, "..", "fonts"), os.path.join(cache, "fonts")):
        if os.path.isfile(os.path.join(d, name)):
            return os.path.join(d, name)
    sys.exit("missing %s: run scripts/setup.sh first" % name)


FONT_R = find_font("Regular")
FONT_B = find_font("Bold")

# hk2s (Hong Kong), tw2s (Taiwan) or t2s (generic); character forms only, no vocabulary changes
cc = opencc.OpenCC(os.environ.get("PDF_T2S_CONFIG", "hk2s"))
FIX = {"㇐": "一", "˴": "、", "ˑ": "、", "˹": "「", "˼": "」"}


def norm(c):
    if c in FIX:
        return FIX[c]
    o = ord(c)
    if 0xF900 <= o <= 0xFAFF or 0x2F800 <= o <= 0x2FA1F or 0x2E80 <= o <= 0x2FDF:
        return unicodedata.normalize("NFKC", c)
    return c


def convert_chars(chars):
    src = "".join(norm(c) for c in chars)
    out = cc.convert(src)
    if len(out) != len(src):
        out = "".join(cc.convert(c) for c in src)
    # OpenCC keeps 於 in a few phrases (e.g. 適用於單); 于 is right in practice
    return out.replace("於", "于")


def is_bold(span):
    return bool(span["flags"] & 16) or any(
        k in span["font"].lower() for k in ("bold", "heavy", "black"))


def fix_tounicode(doc, fontname, used):
    """Noto maps several code points (e.g. 略 and U+F976) to one glyph; make
    copy/search yield the character we actually drew."""
    lines = ["<%04x> <%s>" % (g, "".join("%04x" % b for b in
             [int.from_bytes(c.encode("utf-16-be")[i:i + 2], "big")
              for i in range(0, len(c.encode("utf-16-be")), 2)]))
             for g, c in sorted(used.items())]
    body = []
    for i in range(0, len(lines), 100):
        chunk = lines[i:i + 100]
        body.append("%d beginbfchar\n%s\nendbfchar" % (len(chunk), "\n".join(chunk)))
    cmap = ("/CIDInit /ProcSet findresource begin\n12 dict begin\nbegincmap\n"
            "/CIDSystemInfo <</Registry(Adobe)/Ordering(UCS)/Supplement 0>> def\n"
            "/CMapName /Adobe-Identity-UCS def\n/CMapType 2 def\n"
            "1 begincodespacerange\n<0000> <FFFF>\nendcodespacerange\n%s\n"
            "endcmap\nCMapName currentdict /CMap defineresource pop\nend\nend\n"
            % "\n".join(body))
    for x in range(1, doc.xref_length()):
        if doc.xref_get_key(x, "Subtype")[1] != "/Type0":
            continue
        base = doc.xref_get_key(x, "BaseFont")[1].lstrip("/").replace("#20", "").replace(" ", "")
        if base.split("+")[-1] != fontname.replace(" ", ""):
            continue
        tu = doc.get_new_xref()
        doc.update_object(tu, "<<>>")
        doc.update_stream(tu, cmap.encode())
        doc.xref_set_key(x, "ToUnicode", "%d 0 R" % tu)


def otf_to_ttf(font):
    """Replace CFF outlines with TrueType ones: MuPDF treats glyph ids as CIDs,
    which only holds for glyf-based fonts."""
    from fontTools.pens.cu2quPen import Cu2QuPen
    from fontTools.pens.ttGlyphPen import TTGlyphPen
    from fontTools.ttLib import newTable

    order = font.getGlyphOrder()
    gs = font.getGlyphSet()
    glyf = newTable("glyf")
    glyf.glyphOrder = order
    glyf.glyphs = {}
    for name in order:
        pen = TTGlyphPen(gs)
        gs[name].draw(Cu2QuPen(pen, 1.0, reverse_direction=True))
        glyf[name] = pen.glyph()
    font["loca"] = newTable("loca")
    font["glyf"] = glyf
    del font["CFF "]
    if "VORG" in font:
        del font["VORG"]
    font["maxp"] = newTable("maxp")
    font["maxp"].tableVersion = 0x00010000
    for attr in ("maxZones", "maxTwilightPoints", "maxStorage", "maxFunctionDefs",
                 "maxInstructionDefs", "maxStackElements", "maxSizeOfInstructions",
                 "maxComponentElements"):
        setattr(font["maxp"], attr, 0)
    font["maxp"].maxZones = 1
    font["head"].indexToLocFormat = 0
    font["head"].glyphDataFormat = 0
    font["post"].formatType = 3.0
    font.sfntVersion = "\x00\x01\x00\x00"


def subset_font(path, chars):
    """Return a fitz.Font holding only the glyphs for `chars` (keeps the PDF small)."""
    from fontTools import subset
    from fontTools.ttLib import TTFont
    import io
    opts = subset.Options()
    opts.name_IDs = ["*"]
    opts.notdef_outline = True
    font = TTFont(path)
    sub = subset.Subsetter(opts)
    sub.populate(unicodes=[ord(c) for c in chars])
    sub.subset(font)
    otf_to_ttf(font)
    buf = io.BytesIO()
    font.save(buf)
    return fitz.Font(fontbuffer=buf.getvalue())


def process(src, dst):
    doc = fitz.open(src)
    stats = collections.Counter()
    plan = []  # per page: list of (span, converted chars)
    for page in doc:
        jobs = []
        raw = page.get_text("rawdict", flags=fitz.TEXT_PRESERVE_WHITESPACE)
        for block in raw["blocks"]:
            for line in block.get("lines", []):
                spans = [s for s in line["spans"] if s["chars"]]
                orig = [c["c"] for s in spans for c in s["chars"]]
                new = convert_chars(orig)
                if new == "".join(orig):
                    continue
                k = 0
                for s in spans:
                    n = len(s["chars"])
                    jobs.append((s, new[k:k + n]))
                    k += n
        plan.append(jobs)

    need = {True: set(), False: set()}
    for jobs in plan:
        for s, new in jobs:
            need[is_bold(s)].update(c for c in new if not c.isspace())
    fonts = {b: subset_font(FONT_B if b else FONT_R, need[b] or {"a"}) for b in need}
    used = {b: {} for b in need}  # glyph id -> char actually drawn

    for page, jobs in zip(doc, plan):
        if not jobs:
            continue
        for s, _ in jobs:
            # thin band through the span's centre, so adjacent lines are untouched
            r = fitz.Rect(s["bbox"])
            cy, h = (r.y0 + r.y1) / 2, max(r.height * 0.15, 0.3)
            page.add_redact_annot(fitz.Rect(r.x0 + 0.5, cy - h, r.x1 - 0.5, cy + h), fill=False)
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE,
                              graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                              text=fitz.PDF_REDACT_TEXT_REMOVE)
        writers = {}
        for s, new in jobs:
            bold = is_bold(s)
            font = fonts[bold]
            color = fitz.sRGB_to_pdf(s["color"])
            alpha = s.get("alpha", 255) / 255
            tw = writers.setdefault((color, alpha), fitz.TextWriter(page.rect))
            for ch, c in zip(s["chars"], new):
                if c.isspace():
                    continue
                gid = font.has_glyph(ord(c))
                if not gid:
                    stats["missing:" + c] += 1
                    continue
                tw.append(ch["origin"], c, font=font, fontsize=s["size"])
                used[bold][gid] = c
                stats["chars"] += 1
        for (color, alpha), tw in writers.items():
            tw.write_text(page, color=color, opacity=alpha)
    for bold, font in fonts.items():
        fix_tounicode(doc, font.name, used[bold])
    doc.save(dst, garbage=4, deflate=True)
    return stats


if __name__ == "__main__":
    print(process(sys.argv[1], sys.argv[2]))
