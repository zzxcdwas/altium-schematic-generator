"""Netlist-driven Altium schematic builder using real symbols from the course libraries.

Pipeline:  netlist + placement  ->  .SchDoc (OLE, native)  ->  ERC report

Coordinate units are 1/100 inch (10 mil); the schematic grid is 10 units.

The single most important geometry rule (verified against an Altium-exported
schematic: 164/164 wire endpoints matched, 0 matched the other candidate):

    a pin record's LOCATION is where the pin line leaves the component body;
    the electrical connection point is the far end, LOCATION + dir * PINLENGTH.
"""
import math
import os
import re
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import schlib
import sch_gen
import sch_pack

try:
    import config
except ImportError:                      # 作为包被导入时
    from . import config

# 库目录由环境变量 ALT_LIB_ROOT 指定，缺省时自动探测常见安装位置。
# 见 config.py —— 开源版本不要再写死任何本机路径。
LIBROOT = config.lib_root()

# record types that are pure graphics on a component and can be moved as-is
GRAPHIC_RECORDS = {3, 4, 6, 7, 8, 9, 11, 12, 13, 14, 28, 29}
# record types we never copy out of a library symbol
SKIP_RECORDS = {1, 2, 34, 41, 44, 45, 46, 47, 48}

DIR_VEC = {0: (1, 0), 1: (0, 1), 2: (-1, 0), 3: (0, -1)}
DIR_RIGHT, DIR_UP, DIR_LEFT, DIR_DOWN = 0, 1, 2, 3

_libcache = {}


def load_lib(name):
    """Load a library and normalize every symbol into design space (y-down).

    Library files store symbols in Altium's y-up space; the pipeline (Placed
    hot spots, plan_nets, the emitter's flip) works in y-down design space,
    so converting once at load keeps every consumer consistent.
    """
    if name not in _libcache:
        raw = schlib.load(os.path.join(LIBROOT, name))
        _libcache[name] = {k: v.normalize() for k, v in raw.items()}
    return _libcache[name]


def find_symbol(comp, libs=None):
    """Locate a symbol by name across the course libraries."""
    if libs is None:
        libs = ["10-常见芯片.SchLib", "01-电阻-电容-电感.SchLib", "03-LED发光二极管.SchLib",
                "20-保险丝-晶振-光耦.SchLib", "07-常用按键-开关.SchLib", "02-二极管-整流桥.SchLib",
                "11-电源类芯片.SchLib", "19-CH340系列编程器芯片.SchLib", "54-接插件-脚距2.54 (100mil) .SchLib"]
    for lib in libs:
        try:
            syms = load_lib(lib)
        except Exception:
            continue
        if comp in syms:
            return lib, syms[comp]
    raise KeyError("symbol %r not found in %s" % (comp, libs))


_PROP_RE = re.compile(r"\|([A-Z0-9_]+)=")


_PROP_RE = re.compile(r"\|([A-Za-z0-9_.%]+)=")


def split_props(text):
    """'|A=1|B.C=2' -> [('A','1'), ('B.C','2')], preserving order.

    The key class must include '.' -- Altium writes dotted keys such as
    ``Location.Y`` and ``Corner.X``; dropping them silently deletes the
    component body rectangle.
    """
    out = []
    for m in _PROP_RE.finditer(text):
        start = m.end()
        nxt = text.find("|", start)
        val = text[start:] if nxt < 0 else text[start:nxt]
        out.append((m.group(1), val))
    return out


_X_KEYS = ("LOCATION.X", "CORNER.X")
_Y_KEYS = ("LOCATION.Y", "CORNER.Y")
_POINT_RE = re.compile(r"([XY])(\d+)")


def _is_x(key):
    if key in _X_KEYS:
        return True
    m = _POINT_RE.fullmatch(key)
    return bool(m and m.group(1) == "X")


def _is_y(key):
    if key in _Y_KEYS:
        return True
    m = _POINT_RE.fullmatch(key)
    return bool(m and m.group(1) == "Y")


def _neg_y(text):
    """Negate every Y coordinate in a symbol-local graphic record (used with
    the emission flip so a child graphic mirrors together with its pins)."""
    out = []
    for key, val in split_props(text):
        k = key.upper()
        if k.endswith(".Y") or (k.startswith("Y") and k[1:].isdigit()):
            try:
                val = str(-int(val))
            except ValueError:
                pass
        out.append("|%s=%s" % (key, val))
    return "".join(out)


def offset_record(text, dx, dy):
    """Translate every coordinate in a record by (dx, dy).

    Altium omits properties whose value is 0, so a library polygon can simply
    lack ``X1``.  Copying the record verbatim would leave that vertex at the
    *sheet* origin and render a huge filled shape, so missing coordinates that
    the record implies are written out explicitly.
    """
    pairs = split_props(text)
    have = {k.upper() for k, _ in pairs}
    out = []
    for key, val in pairs:
        try:
            if _is_x(key.upper()):
                val = str(int(val) + dx)
            elif _is_y(key.upper()):
                val = str(int(val) + dy)
        except ValueError:
            pass
        out.append("|%s=%s" % (key, val))

    props = {k.upper(): v for k, v in pairs}

    def add(key, delta):
        if key not in have:
            out.append("|%s=%d" % (key, delta))

    count = props.get("LOCATIONCOUNT")
    if count and count.isdigit():
        n = int(count)
        touched = any(k in have for k in
                      ["X%d" % i for i in range(1, n + 1)] +
                      ["Y%d" % i for i in range(1, n + 1)])
        if touched:
            for i in range(1, n + 1):
                add("X%d" % i, dx)
                add("Y%d" % i, dy)
    # a placed object must never fall back to the sheet origin, so LOCATION is
    # written out for every record type that has one; CORNER only belongs to
    # records that use one.  Polylines/polygons (6/7) address points directly
    # and carry no LOCATION at all.
    LOCATION_RECORDS = {3, 4, 8, 9, 11, 12, 13, 14, 28}
    rectype = props.get("RECORD", "")
    wants_location = rectype.isdigit() and int(rectype) in LOCATION_RECORDS
    if wants_location or any(k.startswith("LOCATION.") for k in have):
        add("LOCATION.X", dx)
        add("LOCATION.Y", dy)
    if any(k.startswith("CORNER") for k in have):
        add("CORNER.X", dx)
        add("CORNER.Y", dy)
    return "".join(out)


class Placed:
    def __init__(self, ref, lib, symbol, x, y, value, footprint):
        self.ref = ref
        self.lib = lib
        self.symbol = symbol
        self.x = x
        self.y = y
        self.value = value
        self.footprint = footprint
        # explicit (dx_desig, dy_desig, dx_val, dy_val) offsets from the part
        # origin; None means "derive from the symbol bounding box"
        self.text_pos = None
        self._hotspots()

    def _hotspots(self):
        """designator -> hot spot (the electrical connection point)"""
        self.pins = {}
        for p in self.symbol.pins:
            length = p.get("length", 20)
            dx, dy = DIR_VEC[p["direction"]]
            hx = self.x + p["x"] + dx * length
            hy = self.y + p["y"] + dy * length
            self.pins[str(p["designator"])] = {
                "x": hx, "y": hy,
                "name": p["name"],
                "electrical": p["electrical"],
                "direction": p["direction"],
                "length": length,
                "rel_x": p["x"], "rel_y": p["y"],
            }

    def relocate(self, x, y):
        """Move the part so its hot spots follow (used by place_pin)."""
        self.x, self.y = x, y
        self._hotspots()
        return self

    def set_text(self, desig_dx, desig_dy, val_dx, val_dy):
        """Pin the designator/value labels to explicit offsets from the origin."""
        self.text_pos = (desig_dx, desig_dy, val_dx, val_dy)
        return self

    def hotspot(self, designator):
        key = str(designator)
        if key not in self.pins:
            raise KeyError("%s has no pin %s (has %s)"
                           % (self.ref, designator, sorted(self.pins)))
        return self.pins[key]

    def bounds(self):
        return self.symbol.bounds()

    def __repr__(self):
        return "<%s %s@(%d,%d) pins=%d>" % (self.ref, self.symbol.name, self.x, self.y, len(self.pins))


class Schematic:
    def __init__(self, width=1150, height=800, title="Sheet1"):
        self.doc = sch_gen.SchDoc(sheet_width=width, sheet_height=height, flip=height)
        self.width = width
        self.height = height
        self.title = title
        self.parts = []
        self.nets = {}          # net name -> list of (ref, pin)
        self.net_wires = {}     # net name -> list of polylines [(x,y),...] drawn verbatim
        self.power = {}         # net name -> (x, y)
        self.notes = []
        self.extra_ports = []   # (name, x, y, orientation, style) drawn verbatim
        self.extra_labels = []  # (name, x, y) drawn verbatim
        # hierarchical-design extras (图7-12 style sheets)
        self.extra_wires = []       # (net_name, [polyline...]) verbatim, may have no pins
        self.sch_ports = []         # (name, x, y) RECORD=18 sheet ports
        self.sheet_symbols = []     # (x, y_top, w, h, name, filename, entries)
        self.extra_junctions = []   # (x, y) manual junction dots

    def hier_wire(self, name, polylines):
        """Register wires for a net that may have NO component pins (e.g. a
        wire joining two sheet entries in a top-level sheet)."""
        self.extra_wires.append((name, [list(p) for p in polylines]))
        return name

    def hier_port(self, name, x, y):
        """RECORD=18 sheet port; the wire attaches at (x, y) = body's left end."""
        self.sch_ports.append((name, x, y))

    def hier_symbol(self, x, y_top, w, h, name, filename, entries):
        """Sheet symbol; entries = [(entry_name, side(0=L,1=R,2=T,3=B), dist)]."""
        self.sheet_symbols.append((x, y_top, w, h, name, filename, list(entries)))

    def hier_junction(self, x, y):
        self.extra_junctions.append((x, y))

    def port(self, name, x, y, style=4, orientation=1):
        """Manually place a power port (used with wire_net for textbook rails)."""
        self.extra_ports.append((name, x, y, orientation, style))

    def label(self, name, x, y):
        """Manually place a net label on an explicitly wired net."""
        self.extra_labels.append((name, x, y))

    # -- placement -------------------------------------------------------
    def add(self, ref, comp, x, y, value=None, footprint=None, lib=None,
            rot=0, mirror=False):
        """Place a library symbol (rot: 0/90/180/270 CCW, mirror: flip x first).

        The transform is baked into the symbol's coordinates so the hot spots
        used for wiring are exactly the pins Altium will render.
        """
        if lib:
            syms = load_lib(lib)
            if comp not in syms:
                raise KeyError("%s not in %s" % (comp, lib))
            used_lib, sym = lib, syms[comp]
        else:
            used_lib, sym = find_symbol(comp)
        if rot or mirror:
            sym = sym.transformed(rot, mirror)
        part = Placed(ref, used_lib, sym, x, y, value or comp, footprint)
        self.parts.append(part)
        return part

    def add_symbol(self, ref, symbol, x, y, value=None, footprint=None,
                   rot=0, mirror=False):
        """Place a pre-built symbol object (library symbol or a synthetic one).

        The symbol only needs to expose: name, props (dict, may have DISPLAYMODE),
        children (list of (props_dict, raw_text)), pins (list of dicts with keys
        designator/name/x/y/direction/electrical/length), and bounds().
        rot/mirror bake the placement transform into the symbol coordinates
        (same convention as add()).
        """
        if rot or mirror:
            symbol = symbol.transformed(rot, mirror)
        part = Placed(ref, getattr(symbol, "lib", "(synthetic)"), symbol, x, y,
                      value or getattr(symbol, "name", ref), footprint)
        self.parts.append(part)
        return part

    def place_pin(self, ref, comp, lib, pin, x, y, rot=0, mirror=False,
                  value=None, footprint=None):
        """Place a part so that pin ``pin``'s hot spot lands exactly on (x, y).

        Library symbols put their origin wherever the symbol author liked
        (Miscellaneous Devices' Cap has its first pin at (-10, +10), the
        74LS47's VCC at (+40, -20) ...).  Anchoring on a pin removes all the
        per-part offset arithmetic from the layout code and makes it impossible
        to wire to a coordinate the part does not actually have.
        """
        part = self.add(ref, comp, 0, 0, value=value, footprint=footprint,
                        lib=lib, rot=rot, mirror=mirror)
        h = part.pins[str(pin)]
        return part.relocate(x - h["x"], y - h["y"])

    def net(self, name, *pins):
        """pins: (ref, '1') tuples -- or a Placed plus pin designator."""
        self.nets.setdefault(name, [])
        for item in pins:
            ref, pin = item
            self.nets[name].append((ref, str(pin)))
        return name

    def wire_net(self, name, polylines):
        """Register explicit wire polylines for a net (pins must already be
        registered via net()).  The polylines are emitted verbatim instead of
        per-pin stubs+labels, so tightly packed chains (decoder -> resistor
        pack -> display) read as real routed wires."""
        self.net_wires.setdefault(name, []).extend(list(p) for p in polylines)
        return name

    def power_port(self, name, x, y, style=4, orientation=1):
        self.power[name] = (x, y, style, orientation)

    @staticmethod
    def is_power(name):
        n = name.upper()
        return n.startswith(("VCC", "VDD", "VSS", "GND", "+5V", "+3V3", "5V", "3V3"))

    def note(self, text, x, y, font_id=1):
        self.notes.append((text, x, y, font_id))

    # -- geometry --------------------------------------------------------
    def _part(self, ref):
        for p in self.parts:
            if p.ref == ref:
                return p
        raise KeyError("no part %r" % ref)

    def _points(self, name):
        pts = []
        for ref, pin in self.nets.get(name, []):
            h = self._part(ref).hotspot(pin)
            pts.append((h["x"], h["y"], ref, pin))
        return pts

    # -- emission --------------------------------------------------------
    def _emit_parts(self):
        for part in self.parts:
            # `or "0"`: empty DISPLAYMODE trips strict parsers ("Invalid int
            # value for DisplayMode").  AD tolerates it, other tools may not.
            dm = part.symbol.props.get("DISPLAYMODE") or "0"
            owner = self.doc.component(part.symbol.name, part.x, part.y,
                                       display_mode=dm,
                                       target="*")
            part.owner = owner
            # designator and value (box-style symbols may want them above)
            b = part.bounds()
            if part.text_pos is not None:
                ddx, ddy, vdx, vdy = part.text_pos
                self.doc.designator(owner, part.ref, part.x + ddx, part.y + ddy)
                self.doc.parameter(owner, "Value", part.value, part.x + vdx,
                                   part.y + vdy, hidden=False, font_id=1)
            elif getattr(part.symbol, "label_above", False):
                self.doc.designator(owner, part.ref, part.x + b[0] - 5, part.y + b[1] - 8)
                self.doc.parameter(owner, "Value", part.value, part.x + b[0] - 5,
                                   part.y + b[3] + 12, hidden=False, font_id=1)
            else:
                self.doc.designator(owner, part.ref, part.x + b[0] - 5, part.y + b[3] + 5)
                self.doc.parameter(owner, "Value", part.value, part.x + b[0] - 5,
                                   part.y + b[1] - 6, hidden=False, font_id=1)
            if part.footprint:
                self.doc.parameter(owner, "Footprint", part.footprint, part.x, part.y,
                                   hidden=True, font_id=1)
            # graphics copied from the library, translated into place.
            # The _neg_y + (flip - y) chain maps ANY record into file space:
            # normalized/hand-drawn symbols carry y-down (visual) offsets,
            # raw library symbols carry y-up offsets -- both land correctly.
            for props, raw in part.symbol.children:
                try:
                    rec = int(props.get("RECORD", -1))
                except ValueError:
                    continue
                if rec in SKIP_RECORDS or rec not in GRAPHIC_RECORDS:
                    continue
                if self.doc.flip:
                    raw = _neg_y(raw)
                    text = offset_record(raw, part.x, self.doc.flip - part.y)
                else:
                    text = offset_record(raw, part.x, part.y)
                # OWNERINDEX points at the component record; spelling differs
                # between libraries (OWNERINDEX vs OwnerIndex), so match
                # case-insensitively and add it only when truly absent.
                m = re.search(r"\|OWNERINDEX=[^|]*", text, re.IGNORECASE)
                if m:
                    text = text[:m.start()] + "|OWNERINDEX=%d" % owner + text[m.end():]
                else:
                    text += "|OWNERINDEX=%d" % owner
                text = self._fix(text, "OWNERPARTID", "1")
                text = self._fix(text, "INDEXINSHEET", str(self.doc.next_isheet()))
                self.doc._emit(text)
            # pins
            show_nm = getattr(part.symbol, "show_pin_names", False)
            show_dg = getattr(part.symbol, "show_pin_designators", False)
            # PINCONGLOMERATE: bit3(0x08)=pin name shown, bit4(0x10)=designator
            # shown, 0x20 = constant bit real AD16 files carry.  Respect the
            # symbol attrs instead of the old hard-wired 56 (show everything).
            #
            # NOTE: every pin must be emitted.  A previous edit had the
            # doc.pin() call nested inside ``if show_dg`` *and* outside the
            # loop, so a part emitted at most its last pin -- and nothing at
            # all once the textbook style hid the designators.
            for desig in sorted(part.pins, key=lambda d: _pin_sort(d)):
                p = part.pins[desig]
                # 0x20 is the constant bit real AD16 files carry; 0x08/0x10
                # turn the pin name/designator text on.  The direction bits
                # (0-1) are added by doc.pin() AFTER the y-flip -- putting
                # them here as well would clobber the flipped code.
                cong = 32
                if show_nm:
                    cong |= 0x08
                if show_dg:
                    cong |= 0x10
                self.doc.pin(owner, desig, p["name"],
                             part.x + p["rel_x"], part.y + p["rel_y"],
                             p["direction"], length=p["length"],
                             electrical=p["electrical"], conglomerate_extra=cong,
                             show_name=show_nm, show_designator=show_dg)

    @staticmethod
    def _fix(text, key, value):
        """Set |key=value|, replacing any existing spelling of the field.

        Library records are inconsistent about case: Miscellaneous Devices
        writes ``INDEXINSHEET`` while 01-电阻-电容-电感.SchLib writes
        ``IndexInSheet``.  A case-sensitive test would append a *second* field
        and strict parsers (altium-monkey) reject the record with
        "duplicate field INDEXINSHEET".
        """
        m = re.search(r"\|%s=([^|]*)" % re.escape(key), text, re.IGNORECASE)
        if m:
            return text[:m.start()] + "|%s=%s" % (key, value) + text[m.end():]
        return text + "|%s=%s" % (key, value)

    def _pin_dir(self, ref, pin):
        try:
            return int(self._part(ref).pins[str(pin)]["direction"]) & 3
        except Exception:
            return 0

    # -- routing plan (shared by the emitter and the SVG preview) ---------
    MAX_WIRE = 900          # MST edges longer than this fall back to labels

    def _bodies(self):
        """Component bounding boxes in absolute coords, shrunk a little so a
        wire that merely touches an edge is not treated as a body crossing."""
        boxes = []
        for p in self.parts:
            b = p.bounds()
            x0, y0 = p.x + b[0], p.y + b[1]
            x1, y1 = p.x + b[2], p.y + b[3]
            boxes.append((min(x0, x1) + 3, min(y0, y1) + 3,
                          max(x0, x1) - 3, max(y0, y1) - 3))
        return boxes

    @staticmethod
    def _seg_hits(p1, p2, boxes, pad=4):
        (x1, y1), (x2, y2) = p1, p2
        steps = int(max(abs(x2 - x1), abs(y2 - y1)))
        if steps == 0:
            return False
        for s in range(1, steps):
            t = s / float(steps)
            px, py = x1 + (x2 - x1) * t, y1 + (y2 - y1) * t
            for bx0, by0, bx1, by1 in boxes:
                if bx0 + pad < px < bx1 - pad and by0 + pad < py < by1 - pad:
                    return True
        return False

    def _poly_ok(self, poly, boxes, pad=1):
        return not any(self._seg_hits(poly[i], poly[i + 1], boxes, pad=pad)
                       for i in range(len(poly) - 1))

    def _route_poly(self, a, b, boxes):
        """Orthogonal route between two points that dodges component bodies.

        Returns None when every candidate crosses a body -- the caller then
        falls back to net labels for that connection.
        """
        (x1, y1), (x2, y2) = a, b
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        cands = []
        if x1 == x2 or y1 == y2:            # already aligned: straight first
            cands.append([(x1, y1), (x2, y2)])
        else:
            cands.append([(x1, y1), (x2, y1), (x2, y2)])
            cands.append([(x1, y1), (x1, y2), (x2, y2)])
        cands.append([(x1, y1), (mx, y1), (mx, y2), (x2, y2)])
        cands.append([(x1, y1), (x1, my), (x2, my), (x2, y2)])
        # Detour lanes: two collinear pins often have a component body sitting
        # right between them (e.g. U1 between U2 and the header), so walk the
        # wire around it instead of giving up and falling back to a label.
        for off in (70, -70, 150, -150, 250, -250, 350, -350):
            cands.append([(x1, y1), (x1, y1 + off), (x2, y1 + off), (x2, y2)])
            cands.append([(x1, y1), (x1 + off, y1), (x1 + off, y2), (x2, y2)])
        for poly in cands:
            if self._poly_ok(poly, boxes, pad=1):
                return poly
        return None

    def _stub(self, x, y, ref, pin, entry, name, length=30):
        dx, dyv = DIR_VEC[self._pin_dir(ref, pin)]
        ex, ey = x + dx * length, y + dyv * length
        entry["wires"].append([(x, y), (ex, ey)])
        entry["labels"].append((name, ex, ey))
        return ex, ey

    def _plan_signal(self, name, pts, boxes, entry):
        """Connect a signal net with REAL wires.

        Prim MST over Manhattan distance: the sheet gets n-1 wires of minimum
        total length, which is exactly how a hand-drawn schematic looks --
        parts wired to their neighbours, no wires through component bodies.
        A pin only falls back to a stub+label when its MST edge is too long or
        no clean route exists.  (The old code emitted stubs+labels for every
        signal net, so the sheet looked completely unwired.)
        """
        n = len(pts)
        if n == 1:
            self._stub(pts[0][0], pts[0][1], pts[0][2], pts[0][3], entry, name)
            return
        used = [False] * n
        used[0] = True
        edges = []
        while len(edges) < n - 1:
            best = None
            for i in range(n):
                if not used[i]:
                    continue
                for j in range(n):
                    if used[j]:
                        continue
                    d = abs(pts[i][0] - pts[j][0]) + abs(pts[i][1] - pts[j][1])
                    if best is None or d < best[0]:
                        best = (d, i, j)
            if best is None:
                break
            used[best[2]] = True
            edges.append(best)
        wired = set()
        for d, i, j in edges:
            if d > self.MAX_WIRE:
                continue
            poly = self._route_poly((pts[i][0], pts[i][1]),
                                    (pts[j][0], pts[j][1]), boxes)
            if poly is None:
                continue
            entry["wires"].append(poly)
            wired.add(i)
            wired.add(j)
        for k in range(n):
            if k not in wired:
                self._stub(pts[k][0], pts[k][1], pts[k][2], pts[k][3], entry, name)

    def plan_nets(self):
        """Wires / labels / power ports for every net (no emission).

        The SVG preview renders from the same plan so the browser and the
        .SchDoc can never disagree.
        """
        boxes = self._bodies()
        plan = {}
        for name in sorted(set(self.nets) | set(self.net_wires) | {n for n, _ in self.extra_wires}):
            pts = self._points(name)
            entry = {"wires": [], "labels": [], "ports": []}
            plan[name] = entry
            if name in self.net_wires:
                for poly in self.net_wires[name]:
                    if len(poly) >= 2:
                        entry["wires"].append([tuple(p) for p in poly])
                continue
            for _, polys in self.extra_wires:
                if _ == name:
                    for poly in polys:
                        if len(poly) >= 2:
                            entry["wires"].append([tuple(p) for p in poly])
            if not pts:
                continue
            if self.is_power(name):
                gnd = name.upper().startswith(("GND", "VSS"))
                style = 4 if gnd else 2
                for x, y, ref, pin in pts:
                    d = self._pin_dir(ref, pin)
                    dx, dy = DIR_VEC[d]
                    ex, ey = x + dx * 20, y + dy * 20
                    entry["wires"].append([(x, y), (ex, ey)])
                    entry["ports"].append((name, ex, ey, d, style))
                continue
            self._plan_signal(name, pts, boxes, entry)
        # manually placed ports / labels join the plan so the SVG preview and
        # the .SchDoc always show the same picture
        for nm, x, y, orient, style in self.extra_ports:
            e = plan.setdefault(nm, {"wires": [], "labels": [], "ports": []})
            e["ports"].append((nm, x, y, orient, style))
        for nm, x, y in self.extra_labels:
            e = plan.setdefault(nm, {"wires": [], "labels": [], "ports": []})
            e["labels"].append((nm, x, y))
        return plan

    def _junctions(self, plan=None):
        """Junction dots for every T-connection (a wire vertex landing inside
        another wire of the SAME net).

        Altium's netlister connects a wire end that touches the interior of
        another wire, but the dot itself has to exist as a RECORD=29 object or
        the sheet renders without it.  Crossings of two *different* nets are
        deliberately excluded -- the textbook's multivibrator cross must stay a
        bare crossing with no dot, or it would read as a short.
        """
        plan = plan or self.plan_nets()
        out = []
        for name, entry in plan.items():
            segs = []
            for poly in entry["wires"]:
                for i in range(len(poly) - 1):
                    segs.append((tuple(poly[i]), tuple(poly[i + 1])))
            verts = []
            for poly in entry["wires"]:
                for p in poly:
                    p = tuple(p)
                    if p not in verts:
                        verts.append(p)
            for v in verts:
                touch = 0
                for a, b in segs:
                    if v == a or v == b:
                        touch += 1
                    elif _on_seg(v, a, b):
                        touch += 2
                if touch >= 3:
                    out.append((v[0], v[1]))
        return out

    def _emit_nets(self):
        plan = self.plan_nets()
        for name, entry in plan.items():
            for poly in entry["wires"]:
                self.doc.wire(poly)
            for nm, x, y in entry["labels"]:
                self.doc.net_label(nm, x, y, orientation=0)
            for nm, x, y, orient, style in entry["ports"]:
                self.doc.power_port(nm, x, y, orientation=orient, style=style)
        for name, x, y in self.sch_ports:
            self.doc.port18(name, x, y)
        for x, y_top, w, h, nm, fn, entries in self.sheet_symbols:
            self.doc.sheet_symbol(x, y_top, w, h, nm, fn, entries)
        for x, y in self.extra_junctions:
            self.doc.junction(x, y)
        for x, y in self._junctions(plan):
            self.doc.junction(x, y)

    def _route(self, a, b, color=8388608):
        """Orthogonal L route between two points; a straight line when already aligned."""
        (x1, y1), (x2, y2) = a, b
        if x1 == x2 or y1 == y2:
            self.doc.wire([(x1, y1), (x2, y2)], color=color)
            return
        # elbow: horizontal first, then vertical
        self.doc.wire([(x1, y1), (x2, y1)], color=color)
        self.doc.wire([(x2, y1), (x2, y2)], color=color)

    def _emit_notes(self):
        for text, x, y, font_id in self.notes:
            self.doc.text(text, x, y, font_id=font_id)

    # -- output ----------------------------------------------------------
    def render(self):
        self._emit_parts()
        self._emit_nets()
        self._emit_notes()
        return self.doc.render()

    def save(self, path):
        text = self.render()
        lines = [ln for ln in text.split("\n") if ln.strip()]
        # sch_pack rebuilds the OLE container around the record text
        return sch_pack.build(lines, path)


def _pin_sort(desig):
    m = re.match(r"(\d+)", desig)
    return (0, int(m.group(1))) if m else (1, 0)


def _on_seg(p, a, b, tol=0.0):
    """True when p lies on segment a-b strictly between its ends."""
    (px, py), (ax, ay), (bx, by) = p, a, b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    if L2 == 0:
        return False
    t = ((px - ax) * dx + (py - ay) * dy) / L2
    if t <= 0 or t >= 1:
        return False
    cx, cy = ax + t * dx, ay + t * dy
    return (px - cx) ** 2 + (py - cy) ** 2 <= tol * tol


def write_prjpcb(path, sch_name, pcb_name=None):
    """Minimal .PrjPCB so AD opens a real project."""
    doc_guid = "{%s}" % str(uuid.uuid4()).upper()
    lines = [
        "[Design_Project]",
        "Version=1.0",
        "DocumentPath=%s" % os.path.basename(sch_name),
        "",
    ]
    if pcb_name:
        lines += ["[Document2]", "DocumentPath=%s" % os.path.basename(pcb_name), ""]
    with open(path, "w", encoding="utf-8", newline="\r\n") as fh:
        fh.write("\n".join(lines))
    return path
