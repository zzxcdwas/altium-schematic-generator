"""Generate Altium ASCII schematic documents.

Discovered format (verified against a real .SchDoc exported as ASCII):
  line 1        |HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=n
  line 2        |RECORD=31|...            sheet setup
  then          object records, one per line, each starting with |RECORD=<n>|

Index rules:
  OWNERINDEX / INDEXINSHEET count design objects in file order, but the HEADER and the
  sheet record do not take an index, so the first component is index 1 and a record on
  file line N has index N-2.
  INDEXINSHEET is a separate global counter that increments for parameters, designators,
  graphics, wires, net labels, ports and junctions (pins and implementation lists skip it).

Coordinates are in 1/100 inch; _FRAC is the 1/100000 inch remainder.
"""
import math
import time
import uuid

SHEET_TEMPLATE = ("|RECORD=31|FONTIDCOUNT=3|SIZE1=10|FONTNAME1=Times New Roman|SIZE2=7|FONTNAME2=default"
                  "|SIZE3=10|FONTNAME3=Times New Roman|USEMBCS=T|ISBOC=T|HOTSPOTGRIDON=T|HOTSPOTGRIDSIZE=4"
                  "|SHEETSTYLE=17|SYSTEMFONT=1|BORDERON=T|SHEETNUMBERSPACESIZE=4|AREACOLOR=16317695"
                  "|SNAPGRIDON=T|VISIBLEGRIDON=T|SNAPGRIDSIZE=10|VISIBLEGRIDSIZE=10"
                  "|CUSTOMX=%d|CUSTOMY=%d|USECUSTOMSHEET=T|CUSTOMXZONES=%d|CUSTOMYZONES=%d"
                  "|CUSTOMMARGINWIDTH=20|DISPLAY_UNIT=4")


def sheet_record(width, height, zones_x=6, zones_y=4):
    return SHEET_TEMPLATE % (width, height, zones_x, zones_y)

# pin direction codes for PINCONGLOMERATE bits 0..1
DIR_RIGHT, DIR_UP, DIR_LEFT, DIR_DOWN = 0, 1, 2, 3


def u_key():
    return uuid.uuid4().hex


def utf8_sidecar(field, value):
    """Altium writes a `%UTF8%<FIELD>` twin whenever text is non-ASCII.

    This file is serialised as UTF-8, but Altium's own convention is to keep an
    ASCII-safe `TEXT=` copy *and* a `%UTF8%TEXT=` sidecar.  Without the sidecar,
    strict readers must guess the encoding and warn
    ("Recovered unmarked UTF-8 in Altium text record").
    """
    if any(ord(ch) > 127 for ch in value):
        return "|%UTF8%" + field + "=" + value
    return ""


def coord(value):
    """Split a coordinate in 1/100 inch into integer and fractional parts."""
    whole = math.floor(value)
    frac = int(round((value - whole) * 100000))
    if frac >= 100000:
        whole += 1
        frac -= 100000
    return int(whole), frac


class SchDoc:
    def __init__(self, sheet_width=400, sheet_height=300, flip=0):
        self.records = []          # list of strings already fully formed
        self.index = 0             # design object counter (HEADER and sheet are not counted)
        self.isheet = 0            # INDEXINSHEET counter
        self.sheet = sheet_record(sheet_width, sheet_height)
        # flip = K > 0 mirrors the whole sheet vertically at the emission
        # boundary (y -> K - y, pin/port direction codes 1<->3).  Layout code
        # can then keep its intuitive top-down coordinates while the .SchDoc
        # (whose file coordinates are y-up) renders exactly as designed.
        self.flip = flip

    def _fy(self, y):
        return self.flip - y if self.flip else y

    @staticmethod
    def _is_y_prefix(prefix):
        return prefix.endswith(".Y") or (prefix.startswith("Y") and prefix[1:].isdigit())

    def _flip_dir(self, d):
        return {0: 0, 1: 3, 2: 2, 3: 1}.get(d, d) if self.flip else d

    # -- low level -------------------------------------------------------
    def _emit(self, text, counts_index=True):
        self.records.append(text)
        if counts_index:
            self.index += 1
            return self.index
        return None

    def _x(self, prefix, value):
        """Coordinates are 1/100 inch; the _FRAC part is written only when non-zero,
        matching what Altium itself emits.  Y values go through the flip."""
        whole, frac = coord(self._fy(value) if self._is_y_prefix(prefix) else value)
        if frac == 0:
            return "|%s=%d" % (prefix, whole)
        return "|%s=%d|%s_FRAC=%d" % (prefix, whole, prefix, frac)

    def next_isheet(self):
        self.isheet += 1
        return self.isheet

    # -- objects ---------------------------------------------------------
    # display_mode: 备用符号 / 图形模式。AD 自身对单模式器件写具体名称或索引，
    # 留空会被严格解析器判为 "Invalid int value for DisplayMode"，故默认 "0"。
    def component(self, lib_reference, x, y, orientation=0, display_mode="0", target="*"):
        """Place a component and remember its index for the child records."""
        text = ("|RECORD=1" + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y)
                + "|ORIENTATION=%d|LIBREFERENCE=%s|SHOWHIDDENPINS=F|CURRENTPARTID=1"
                  "|DISPLAYMODE=%s|ISMIRRORED=F|PARTIDLOCKED=F|TARGETFILENAME=%s|UNIQUEID=%s"
                % (orientation, lib_reference, display_mode, target, u_key()))
        component_index = self._emit(text)
        # hidden bookkeeping parameter, mirrors what AD always writes
        self.parameter(component_index, "Comment", lib_reference, x, y, hidden=True)
        return component_index

    def designator(self, owner, text, x, y, font_id=2, hidden=False, color=8388608):
        rec = ("|RECORD=34|COLOR=%d" % color + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y)
               + "|OWNERINDEX=%d|OWNERPARTID=-1|INDEXINSHEET=%d|FONTID=%d|NAME=Designator|TEXT=%s"
                 "|SHOWNAME=F|ISHIDDEN=%s|ORIENTATION=0|JUSTIFICATION=0"
               % (owner, self.next_isheet(), font_id, text, "T" if hidden else "F")
               + utf8_sidecar("TEXT", text))
        self._emit(rec)

    def parameter(self, owner, name, text, x, y, hidden=True, font_id=1, color=0):
        rec = ("|RECORD=41|COLOR=%d" % color + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y)
               + "|OWNERINDEX=%d|OWNERPARTID=-1|INDEXINSHEET=%d|FONTID=%d|NAME=%s|TEXT=%s"
                 "|SHOWNAME=F|ISHIDDEN=%s|ORIENTATION=0|JUSTIFICATION=0"
               % (owner, self.next_isheet(), font_id, name, text, "T" if hidden else "F")
               + utf8_sidecar("TEXT", text) + utf8_sidecar("NAME", name))
        self._emit(rec)

    def rectangle(self, owner, x1, y1, x2, y2, color=136, line_width=1, solid=False,
                  area_color=None):
        """Rectangle. Altium writes AREACOLOR and TRANSPARENT here, and LINEWIDTH is an
        enumeration (0 smallest .. 3 large), not a width in mils."""
        fills = area_color if area_color is not None else color
        rec = ("|RECORD=14|OWNERINDEX=%d|OWNERPARTID=1|OWNERPARTDISPLAYMODE=0|ISNOTACCESIBLE=T"
               "|INDEXINSHEET=%d" % (owner, self.next_isheet())
               + self._x("LOCATION.X", x1) + self._x("LOCATION.Y", y1)
               + self._x("CORNER.X", x2) + self._x("CORNER.Y", y2)
               + "|COLOR=%d|AREACOLOR=%d|ISSOLID=%s|TRANSPARENT=T|LINEWIDTH=%d"
               % (color, fills, "T" if solid else "F", line_width))
        self._emit(rec)

    def polyline(self, owner, points, color=None, line_width=1):
        text = ("|RECORD=6|OWNERINDEX=%d|OWNERPARTID=1|OWNERPARTDISPLAYMODE=0|ISNOTACCESIBLE=T"
                "|INDEXINSHEET=%d|LINEWIDTH=%d|LOCATIONCOUNT=%d"
                % (owner, self.next_isheet(), line_width, len(points)))
        for i, (px, py) in enumerate(points, 1):
            text += self._x("X%d" % i, px) + self._x("Y%d" % i, py)
        if color is not None:
            text += "|COLOR=%d" % color
        self._emit(text)

    def pin(self, owner, designator, name, x, y, direction, length=10, electrical=4,
            conglomerate_extra=48, show_name=True, show_designator=True):
        """x, y is the electrical (connection) end of the pin.

        PINCONGLOMERATE 必须是单个无符号字节（真实 AD 文件里取值如 32/34）。
        早期版本把 show_name/show_designator 编进 0x0100/0x0200，导致该字段
        溢出到 568/826，被严格的解析器（altium-monkey）判定为非法。
        这两个高位在 Altium 里从不生效（低 8 位取值与合法图一致），故钳位丢弃。
        """
        direction = self._flip_dir(direction)
        # PINCONGLOMERATE bits 0-1 ARE the direction, so the caller's extra
        # flags must never carry a direction of their own.  Masking them off
        # here is what keeps flipped (up/down) pins pointing the right way:
        # a caller that prefixed ``32 | design_direction`` used to OR the
        # *unflipped* code straight back over the flipped one, so every pin
        # drawn upwards ended up pointing down -- its connection point landed
        # a full pin-length away from the wire and Altium saw it as open.
        conglomerate = (direction | (conglomerate_extra & 0xFC)) & 0xFF
        rec = ("|RECORD=2|OWNERINDEX=%d|OWNERPARTID=1|OWNERPARTDISPLAYMODE=0|ISNOTACCESIBLE=T"
               "|ELECTRICAL=%d|SYMBOL_INNER=0|SYMBOL_INNEREDGE=0|SYMBOL_OUTER=0|SYMBOL_OUTEREDGE=0"
               "|COLOR=136|FONTID=3|DESIGNATOR=%s|NAME=%s|PINCONGLOMERATE=%d"
               % (owner, electrical, designator, name, conglomerate)
               + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y)
               + "|PINLENGTH=%d" % length)
        self._emit(rec)

    def wire(self, points, color=8388608, line_width=1):
        text = ("|RECORD=27|INDEXINSHEET=%d|OWNERPARTID=-1|LINEWIDTH=%d|COLOR=%d|LOCATIONCOUNT=%d"
                % (self.next_isheet(), line_width, color, len(points)))
        for i, (px, py) in enumerate(points, 1):
            text += self._x("X%d" % i, px) + self._x("Y%d" % i, py)
        self._emit(text)

    def junction(self, x, y, color=204, size=1):
        rec = ("|RECORD=29|INDEXINSHEET=%d" % self.next_isheet() + self._x("LOCATION.X", x)
               + self._x("LOCATION.Y", y) + "|COLOR=%d|SIZE=%d" % (color, size))
        self._emit(rec)

    def net_label(self, text, x, y, orientation=0, color=16711680, font_id=1):
        rec = ("|RECORD=25|INDEXINSHEET=%d" % self.next_isheet() + self._x("LOCATION.X", x)
               + self._x("LOCATION.Y", y)
               + "|ORIENTATION=%d|COLOR=%d|FONTID=%d|TEXT=%s" % (orientation, color, font_id, text)
               + utf8_sidecar("TEXT", text))
        self._emit(rec)

    def power_port(self, text, x, y, orientation=1, style=4, color=0):
        rec = ("|RECORD=17|INDEXINSHEET=%d" % self.next_isheet() + self._x("LOCATION.X", x)
               + self._x("LOCATION.Y", y)
               + "|ORIENTATION=%d|COLOR=%d|STYLE=%d|TEXT=%s|SHOWNETNAME=T"
               % (self._flip_dir(orientation), color, style, text)
               + utf8_sidecar("TEXT", text))
        self._emit(rec)

    def text(self, text, x, y, font_id=1, color=0, orientation=0):
        rec = ("|RECORD=4|INDEXINSHEET=%d" % self.next_isheet() + self._x("LOCATION.X", x)
               + self._x("LOCATION.Y", y)
               + "|ORIENTATION=%d|JUSTIFICATION=1|COLOR=%d|FONTID=%d|TEXT=%s"
               % (orientation, color, font_id, text) + utf8_sidecar("TEXT", text))
        self._emit(rec)

    def port18(self, name, x, y, style=3, width=30, color=128, area_color=8454143):
        """Sheet port (RECORD=18), the thing that pairs with a sheet entry by name.

        Field set mirrors genuine AD16 files (Bluetooth Sentinel/Host_Controller):
        LOCATION is the port body's LEFT end and the body extends WIDTH to the
        right; both ends are electrical connection points for horizontal styles
        (0-3).  x/y are design-space (y-down) and go through the normal flip.
        """
        rec = ("|RECORD=18|INDEXINSHEET=%d|OWNERPARTID=-1|STYLE=%d|WIDTH=%d"
               % (self.next_isheet(), style, width)
               + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y)
               + "|COLOR=%d|FONTID=1|AREACOLOR=%d|NAME=%s|HEIGHT=10"
               % (color, area_color, name)
               + utf8_sidecar("NAME", name))
        self._emit(rec)

    def sheet_symbol(self, x, y_top, w, h, name, filename, entries=(),
                     area_color=8454016):
        """Hierarchical sheet symbol (RECORD=15) + entries (16) + labels (32/33).

        x, y_top is the design-space (y-down) TOP-LEFT corner; the box extends
        right by w and DOWN by h (in file space LOCATION.Y is the top edge and
        the box grows towards smaller y -- verified against AD16 samples with
        altium-monkey: an entry's y is LOCATION.Y - DISTANCEFROMTOP*10).

        entries: iterable of (name, side, distance_from_top) where side is
        0=left, 1=right, 2=top, 3=bottom and distance is counted in 10-unit
        grid steps from the top edge.
        """
        idx = self._emit("|RECORD=15|INDEXINSHEET=%d|OWNERPARTID=-1" % self.next_isheet()
                         + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y_top)
                         + "|XSIZE=%d|YSIZE=%d|COLOR=128|AREACOLOR=%d|ISSOLID=T|UNIQUEID=%s"
                           "|SYMBOLTYPE=Normal" % (w, h, area_color, u_key()))
        for nm, side, dist in entries:
            self._emit("|RECORD=16|OWNERINDEX=%d|OWNERPARTID=-1|SIDE=%d|DISTANCEFROMTOP=%d"
                       "|AREACOLOR=8454143|TEXTFONTID=1|TEXTSTYLE=Full|NAME=%s"
                       "|ARROWKIND=Block & Triangle" % (idx, side, dist, nm)
                       + utf8_sidecar("NAME", nm))
        # sheet name sits 10 above the top edge in design space, the filename
        # right on it -- exactly the offsets real AD16 files carry.
        self._emit("|RECORD=32|OWNERINDEX=%d|INDEXINSHEET=-1|OWNERPARTID=-1" % idx
                   + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y_top - 10)
                   + "|FONTID=6|TEXT=%s" % name + utf8_sidecar("TEXT", name))
        self._emit("|RECORD=33|OWNERINDEX=%d|INDEXINSHEET=-1|OWNERPARTID=-1" % idx
                   + self._x("LOCATION.X", x) + self._x("LOCATION.Y", y_top)
                   + "|FONTID=1|TEXT=%s" % filename + utf8_sidecar("TEXT", filename))
        return idx

    # -- output ----------------------------------------------------------
    def render(self):
        head = "|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=%d" % len(self.records)
        return "\n".join([head, self.sheet] + self.records) + "\n"

    def save(self, path):
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(self.render())
        return path


def demo_resistor(doc, ref, value, x, y, horizontal=True, line_width=1):
    """A resistor symbol built in-place, so the sheet shows graphics without needing the library."""
    owner = doc.component("RES2", x, y, display_mode="RES2")
    doc.designator(owner, ref, x + 0.5, y + 1.5)
    doc.parameter(owner, "Value", value, x - 1.5, y - 2.5, hidden=True)
    if horizontal:
        doc.rectangle(owner, x - 4, y - 3, x + 4, y + 3, line_width=line_width)
        doc.pin(owner, "1", "1", x - 10, y, DIR_RIGHT, length=6)
        doc.pin(owner, "2", "2", x + 10, y, DIR_LEFT, length=6)
    else:
        doc.rectangle(owner, x - 3, y - 4, x + 3, y + 4, line_width=line_width)
        doc.pin(owner, "1", "1", x, y + 10, DIR_DOWN, length=6)
        doc.pin(owner, "2", "2", x, y - 10, DIR_UP, length=6)
    return owner


if __name__ == "__main__":
    import os
    doc = SchDoc()
    doc.text("AD16 console - generator smoke test", 20, 108, font_id=1)
    demo_resistor(doc, "R1", "10K", 80, 100, horizontal=True)
    doc.wire([(60, 100), (70, 100)])
    doc.wire([(90, 100), (100, 100)])
    doc.net_label("NET_A", 60, 100, orientation=1)
    doc.power_port("GND", 100, 100, orientation=1)
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "out")
    os.makedirs(out_dir, exist_ok=True)
    path = doc.save(os.path.join(out_dir, "smoke_test.SchDoc"))
    print(path)
