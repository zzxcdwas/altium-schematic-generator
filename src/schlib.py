"""Read Altium binary .SchLib files and extract component symbols.

A .SchLib is an OLE compound file. The ``FileHeader`` stream holds the whole
library as a framed record stream, identical in framing to .SchDoc:

    <uint16 LE length><0x00><uint8 type><payload>

``payload`` is ``|KEY=VAL|...`` text plus a trailing NUL.  Inside, ``RECORD=1``
starts a component; everything that follows with ``OWNERINDEX`` pointing at it
belongs to it (pins RECORD=2, graphics, designator RECORD=34, parameters
RECORD=41 ...).
"""
import os
import re
import struct
import tempfile
import zlib

import cfb_reader

HEADER_RE = re.compile(r"\|HEADER=([^|]*)")


def read_streams(path):
    """Return {stream_name: bytes} for an OLE compound file."""
    ole = cfb_reader.open_file(path)
    out = {}
    for name in ole.listdir():
        try:
            out[name] = ole.openstream(name)
        except Exception:
            pass
    return out


def parse_records(blob):
    """Split a framed protel record stream into raw payload bytes.

    Framing is ``<uint16 LE length><uint16 LE flags><payload[length]>``.  Both
    .SchLib component streams and .SchDoc use it; in a library some payloads are
    ``|KEY=VAL|`` text and some (notably pins) are binary.
    """
    recs = []
    pos = 0
    n = len(blob)
    while pos + 4 <= n:
        length, flags = struct.unpack_from("<HH", blob, pos)
        if length == 0 or pos + 4 + length > n:
            break
        recs.append((flags, blob[pos + 4: pos + 4 + length]))
        pos += 4 + length
    return recs


# Altium pin electrical types
ELECTRICAL = ["Input", "IO", "Output", "OpenCollector", "Passive",
              "HiZ", "OpenEmitter", "Power"]


def _tail_strings(tail):
    """Parse the trailing ``<len><name><len><designator>`` pair of a pin record.

    Every binary pin ends with::

        <len> <pin name> <len> <pin designator> 0 0 0

    optionally preceded by padding zero bytes.  Leading zeros are skipped, so
    the caller does not need to know how many there are.
    """
    j = 0
    n = len(tail)
    while j < n and tail[j] == 0:
        j += 1
    if j >= n:
        return "", ""
    nl = tail[j]
    name = tail[j + 1: j + 1 + nl].decode("latin1")
    k = j + 1 + nl
    if k >= n:
        return name, ""
    dl = tail[k]
    des = tail[k + 1: k + 1 + dl].decode("latin1")
    return name, des


def decode_pin(payload):
    """Decode a binary pin record (flag 0x0100) from a .SchLib.

    One layout covers both flavours Altium writes::

        [0..11]   fixed header
        [12]      uint8 length of the pin's *group* name
        [13..]    that name (empty in most parts; "Cathode" in Dpy parts)
        p = 13 + group_len
        p+0       always 0x01
        p+1       electrical type
        p+2       bits 0-1 are the direction  (0=right 1=up 2=left 3=down, y-up)
        p+3       pin length
        p+4       always 0x00
        p+5..6    int16 X (symbol-relative)
        p+7..8    int16 Y
        then      <len><name><len><designator> 0 0 0

    The group name is what makes the naive fixed-offset reading fail: parts
    such as Dpy Blue-CA carry a 7- or 12-character name there, shifting every
    following field.  All course-library parts and Miscellaneous Devices have
    an empty group name, which is why they used to work by luck.
    """
    if len(payload) < 28:
        return None
    group_len = payload[12]
    p = 13 + group_len
    if group_len > 64 or p + 9 > len(payload):
        return None
    x, y = struct.unpack_from("<hh", payload, p + 5)
    name, designator = _tail_strings(payload[p + 9:])
    if not designator:
        return None
    return {
        "designator": designator,
        "name": name,
        "x": x, "y": y,
        "direction": payload[p + 2] & 3,
        "electrical": payload[p + 1],
        "length": payload[p + 3] or 20,
        # byte 7 of the fixed header holds the zero-based part index.  Parts
        # with PartCount=2 (74LS47, Dpy Blue-CA ...) otherwise yield two pins
        # per designator and every net gets wired to the wrong half.
        "part": payload[7] + 1,
        "raw": payload,
    }


def parse_props(text):
    """'|A=1|B=2' -> {'A': '1', 'B': '2'}"""
    props = {}
    for chunk in text.split("|"):
        if not chunk:
            continue
        key, _, val = chunk.partition("=")
        props[key] = val
    return props


def _split_keep_order(text):
    """'|A=1|B.C=2' -> [('A','1'), ('B.C','2')] preserving order."""
    out = []
    for chunk in text.split("|"):
        if not chunk:
            continue
        key, _, val = chunk.partition("=")
        out.append((key, val))
    return out


_PAIR_KEYS = [("LOCATION.X", "LOCATION.Y"), ("CORNER.X", "CORNER.Y")]


def _tf_record_text(raw, pt):
    """Apply point transform ``pt`` to every coordinate pair in a record text.

    Altium omits properties whose value is 0, so a vertex may only carry X or
    Y -- missing partners are materialised as 0 before transforming, exactly
    like sch_build.offset_record does for translation.

    Key matching is CASE-INSENSITIVE: Miscellaneous Devices writes
    ``LOCATION.Y`` while 01-电阻-电容-电感 / 04-三极管 write ``Location.Y``.
    A case-sensitive match silently skipped half of those records, leaving the
    symbol's outline un-mirrored next to correctly mirrored pins.
    """
    pairs = _split_keep_order(raw)
    upper = {k.upper(): (k, v) for k, v in pairs}
    point_re = re.compile(r"^([XY])(\d+)$")

    def pair_for(key):
        m = point_re.match(key.upper())
        if m:
            return ("Y%s" % m.group(2)) if m.group(1) == "X" else ("X%s" % m.group(2))
        for kx, ky in _PAIR_KEYS:
            if key.upper() == kx:
                return ky
            if key.upper() == ky:
                return kx
        return None

    def is_x_key(key):
        return key.upper().endswith(".X") or (
            key[:1].upper() == "X" and key[1:].isdigit())

    def value_of(key):
        """Value stored under ``key`` ignoring case (None when absent)."""
        got = upper.get(key.upper())
        return None if got is None else got[1]

    out_map = {}
    consumed = set()
    for key, val in pairs:
        partner = pair_for(key)
        if partner is None or value_of(partner) is None or key in consumed:
            continue
        kx = key if is_x_key(key) else partner
        ky = partner if kx == key else key
        nx, ny = pt(int(value_of(kx)), int(value_of(ky)))
        out_map[kx], out_map[ky] = str(nx), str(ny)
        consumed.update((kx, ky))

    rebuilt = []
    for key, val in pairs:
        if key in consumed:
            rebuilt.append((key, out_map[key]))
            continue
        partner = pair_for(key)
        if partner is not None and value_of(partner) is None:
            # lone coordinate: transform with a 0 filler and write both axes
            if is_x_key(key):
                nx, ny = pt(int(val), 0)
                rebuilt.append((key, str(nx)))
                rebuilt.append((partner, str(ny)))
            else:
                nx, ny = pt(0, int(val))
                rebuilt.append((key, str(ny)))
                rebuilt.append((partner, str(nx)))
            consumed.add(partner)
            continue
        rebuilt.append((key, val))
    return "|" + "|".join("%s=%s" % (k, v) for k, v in rebuilt)


def _num(props, key, default=0):
    v = props.get(key, "")
    try:
        return int(v)
    except ValueError:
        try:
            return float(v)
        except ValueError:
            return default


_ANGLE_RE = re.compile(r"(\|)(STARTANGLE|ENDANGLE)(=)(-?\d+(?:\.\d+)?)(?=\||$)", re.IGNORECASE)


def _shift_arc_angles(raw, delta):
    r"""Add ``delta`` degrees to STARTANGLE/ENDANGLE in a record text.

    Arc records (RECORD=12, also elliptical arcs / pie charts) carry their
    sweep as STARTANGLE/ENDANGLE.  ``transformed()`` rotates every *point* of
    a symbol, but an arc's center alone does not define its geometry: the
    sweep must rotate with the body.  Derivation (verified against the real
    AD16 render of a rotated Inductor): the y-flip between library space and
    design space cancels against the emitter's write flip, so the stored file
    angle is simply lib angle + rotation.  Example: lib Inductor humps span
    90..180/360..90 (bulge up, horizontal inductor); after rot=270 they must
    span 0..90/270..360 (bulge sideways, vertical inductor with the hump
    diameters ALONG the pin axis).  Skipping this turns each hump into a
    disconnected arch and the coil falls apart visually.

    Note: ``(?=\||$)`` -- _tf_record_text rebuilds the record without a
    trailing pipe, so the last key must also match at end-of-string.
    """
    def repl(m):
        val = (float(m.group(4)) + delta) % 360.0
        return "%s%s%s%.3f" % (m.group(1), m.group(2), m.group(3), val)
    return _ANGLE_RE.sub(repl, raw)


class Symbol:
    """A schematic symbol: graphics + pins, all relative to the symbol origin."""

    def __init__(self, name):
        self.name = name
        self.props = {}
        self.children = []          # list of (record_props, raw_text) - graphics etc.
        self.binary = []            # list of (flags, bytes) we could not decode
        self.pins = []              # list of dicts
        self.designator = None
        self.parameters = {}
        self.part = 1               # which part of a multi-part component

    def bounds(self):
        """Bounding box of the symbol in its own coordinate system.

        Reads the *raw* record text rather than the cached props dict: after
        transformed()/normalize() only the raw text carries the transformed
        coordinates, so props would report the untransformed box and the
        designator/value of a rotated part would be placed in the wrong spot.
        """
        xs, ys = [], []
        for props, raw in self.children:
            if raw:
                props = parse_props(raw)
            up = {k.upper(): v for k, v in props.items()}
            if "LOCATION.X" in up:
                xs.append(_num(up, "LOCATION.X"))
                ys.append(_num(up, "LOCATION.Y"))
            if "CORNER.X" in up:
                xs.append(_num(up, "CORNER.X"))
                ys.append(_num(up, "CORNER.Y"))
            for i in range(1, 33):
                kx, ky = "X%d" % i, "Y%d" % i
                if kx in up:
                    xs.append(_num(up, kx))
                    ys.append(_num(up, ky))
        for p in self.pins:
            xs.append(p["x"])
            ys.append(p["y"])
        if not xs:
            return 0, 0, 0, 0
        return min(xs), min(ys), max(xs), max(ys)

    def children_props(self):
        return [props for props, _ in self.children]

    def normalize(self):
        """Library space (y-up) -> design space (y-down, the convention the
        whole build pipeline uses): y := -y on pins and graphics, direction
        codes 1<->3.  Marks the result design_space=True so the emitter skips
        its own library-space flip."""
        out = Symbol(self.name)
        out.props = dict(self.props)
        out.designator = self.designator
        out.parameters = dict(self.parameters)
        out.part = self.part
        out.show_pin_names = getattr(self, "show_pin_names", False)
        out.show_pin_designators = getattr(self, "show_pin_designators", False)
        out.label_above = getattr(self, "label_above", False)
        out.lib = getattr(self, "lib", None)
        out.design_space = True
        flip = {1: 3, 3: 1}
        for p in self.pins:
            q = dict(p)
            q["y"] = -p["y"]
            q["direction"] = flip.get(p["direction"], p["direction"])
            out.pins.append(q)
        for props, raw in self.children:
            out.children.append((props, _tf_record_text(raw, lambda x, y: (x, -y))))
        return out

    def transformed(self, rot=0, mirror=False):
        """Return a copy with rotation/mirror baked into every coordinate.

        Works in design space (y-down), the space normalized()/hand-drawn
        symbols live in.  ``rot`` is counter-clockwise as seen on screen,
        ``mirror`` flips x first.  Direction codes: 0=right 1=down 2=left
        3=up.  We always place with ORIENTATION=0 / ISMIRRORED=F and do the
        math here, so the pins we wire to are, by construction, the pins
        Altium renders.
        """
        if rot not in (0, 90, 180, 270):
            raise ValueError("rot must be 0/90/180/270")

        def pt(x, y):
            if mirror:
                x = -x
            if rot == 90:       # visual CCW 90 in y-down space
                return y, -x
            if rot == 180:
                return -x, -y
            if rot == 270:
                return -y, x
            return x, y

        def dr(d):
            if mirror and d in (0, 2):
                d = 2 - d
            return (d + (4 - rot // 90)) % 4

        out = Symbol(self.name)
        out.props = dict(self.props)
        out.designator = self.designator
        out.parameters = dict(self.parameters)
        out.part = self.part
        out.show_pin_names = getattr(self, "show_pin_names", False)
        out.show_pin_designators = getattr(self, "show_pin_designators", False)
        out.label_above = getattr(self, "label_above", False)
        out.lib = getattr(self, "lib", None)
        out.design_space = getattr(self, "design_space", False)
        for p in self.pins:
            nx, ny = pt(p["x"], p["y"])
            q = dict(p)
            q["x"], q["y"], q["direction"] = nx, ny, dr(p["direction"])
            out.pins.append(q)
        # arcs (and any record with a sweep angle) rotate with the body;
        # mirror reverses the visual rotation direction (see _shift_arc_angles)
        delta = (180 - rot) % 360 if mirror else rot
        for props, raw in self.children:
            raw = _tf_record_text(raw, pt)
            if "STARTANGLE=" in raw.upper() or "ENDANGLE=" in raw.upper():
                raw = _shift_arc_angles(raw, delta)
            out.children.append((props, raw))
        return out

    def __repr__(self):
        return "<Symbol %s pins=%d children=%d>" % (self.name, len(self.pins), len(self.children))


def load(path, part=1):
    """Parse a .SchLib (or compiled .IntLib) into {component_name: Symbol}.

    .IntLib = OLE compound file whose 'SchLib/0.schlib' stream is a
    zlib-compressed inner .SchLib (leading 0x02 marker byte = zlib).  Inner
    layout is the same: FileHeader stream + one storage per component.

    ``part`` selects which part of a multi-part component to build (see
    _parse_symbol); parts are numbered from 1.
    """
    if path.lower().endswith(".intlib"):
        outer = cfb_reader.open_file(path)
        raw = outer.openstream("SchLib/0.schlib")
        if raw[:1] == b"\x02":
            raw = raw[1:]
        blob = zlib.decompress(raw)
        ole = cfb_reader.OleReader(blob)
    else:
        ole = cfb_reader.open_file(path)
    symbols = {}
    for comp_name in ole.list_storages():
        try:
            blob = ole.openstream(comp_name + "/Data")
        except Exception:
            continue
        symbols[comp_name] = _parse_symbol(comp_name, blob, part)
    return symbols


def _parse_symbol(name, blob, part=1):
    """Parse one component storage.

    Multi-part components (PartCount > 1) store every part's pins and graphics
    in the same ``Data`` stream, told apart by ``OWNERPARTID`` (text records)
    and byte 7 of the pin header (binary pins).  Without filtering, 74LS47
    yields 32 pins and half of them are the wrong part's.  ``part`` selects the
    one we place; Altium itself shows ``CurrentPartId=1``, and that is the
    rectangular textbook symbol.
    """
    records = parse_records(blob)

    sym = Symbol(name)
    sym.part = part
    for flags, payload in records:
        # The 0x0100 flag marks binary pin records.  Trust the flag *before*
        # the '|' sniff: a binary pin payload can start with 0x7C by chance
        # (Dpy Blue-CA in Miscellaneous Devices.IntLib does), and parsing that
        # as text yields garbage pins.
        if flags & 0x0100:
            pin = decode_pin(payload)
            if pin and pin["part"] == part:
                sym.pins.append(pin)
            continue
        if payload[:1] != b"|":
            sym.binary.append((flags, payload))
            continue
        raw = payload.rstrip(b"\x00").decode("utf-8", "replace")
        props = parse_props(raw)
        rec = _num(props, "RECORD", -1)
        if rec == 1:
            sym.props = props           # the component record itself (LIBREFERENCE, PARTCOUNT ...)
            continue
        if rec == 2 and "DESIGNATOR" in props:
            if _num(props, "OWNERPARTID", -1) not in (-1, part):
                continue
            sym.pins.append({
                "designator": props.get("DESIGNATOR", ""),
                "name": props.get("NAME", ""),
                "x": _num(props, "LOCATION.X"),
                "y": _num(props, "LOCATION.Y"),
                "direction": _num(props, "PINCONGLOMERATE") & 3,
                "conglomerate": _num(props, "PINCONGLOMERATE"),
                "length": _num(props, "PINLENGTH", 10),
                "electrical": _num(props, "ELECTRICAL", 4),
                "part": _num(props, "OWNERPARTID", 1),
                "raw": raw,
            })
            continue
        if rec == 34 and props.get("NAME") == "Designator":
            sym.designator = props.get("TEXT", "")
            continue
        if rec == 41:
            if _num(props, "OWNERPARTID", -1) not in (-1, part):
                continue
            sym.parameters[props.get("NAME", "")] = props.get("TEXT", "")
            continue
        # graphics / models: keep globals (OWNERPARTID -1) and this part only
        if _num(props, "OWNERPARTID", -1) not in (-1, part):
            continue
        sym.children.append((props, raw))
    return sym


def main():
    import sys
    targets = sys.argv[1:] or ["10-常见芯片.SchLib"]
    root = r"D:\SoftWare\AD16\Documents\Library"
    out = []
    for name in targets:
        path = os.path.join(root, name)
        if not os.path.isfile(path):
            out.append("MISSING " + name)
            continue
        try:
            syms = load(path)
        except Exception as exc:
            out.append("ERROR %s: %r" % (name, exc))
            continue
        out.append("===== %s : %d components =====" % (name, len(syms)))
        for key in sorted(syms):
            s = syms[key]
            b = s.bounds()
            out.append("  %-24s pins=%-3d box=(%d,%d)-(%d,%d)" % (key, len(s.pins), b[0], b[1], b[2], b[3]))
    dest = os.path.join(tempfile.gettempdir(), "altium_lib_dump.txt")
    open(dest, "w", encoding="utf-8").write("\n".join(out))
    print(dest)


if __name__ == "__main__":
    main()
