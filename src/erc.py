"""Electrical rule check for a netlist built with sch_build.

Runs on the model (not on AD), so it reports problems before a file is even
written, and again after generation as a regression gate.
"""
import re

from schlib import ELECTRICAL

# pin types that can drive a net
DRIVERS = {1, 2, 3, 6, 7}       # IO, Output, OpenCollector, OpenEmitter, Power

ERROR = "ERROR"
WARN = "WARN"
INFO = "INFO"


class Issue:
    def __init__(self, level, code, message, where=""):
        self.level = level
        self.code = code
        self.message = message
        self.where = where

    def __str__(self):
        return "[%s] %s %s%s" % (self.level, self.code, self.message,
                                 (" @ " + self.where) if self.where else "")

    def as_dict(self):
        return {"level": self.level, "code": self.code,
                "message": self.message, "where": self.where}


def check(sch):
    """sch is a sch_build.Schematic that has already been populated."""
    issues = []

    # ---- duplicate designators -------------------------------------------
    seen = {}
    for p in sch.parts:
        if p.ref in seen:
            issues.append(Issue(ERROR, "DUP-REF",
                                "duplicate designator %s" % p.ref, p.ref))
        seen[p.ref] = p

    # ---- pin coverage -----------------------------------------------------
    connected = {}          # ref -> set(pin designators)
    for name, pins in sch.nets.items():
        for ref, pin in pins:
            connected.setdefault(ref, set()).add(str(pin))

    pins_by_net = {}
    for name in sch.nets:
        for ref, pin in sch.nets[name]:
            pins_by_net.setdefault(name, []).append((ref, str(pin)))

    for part in sch.parts:
        used = connected.get(part.ref, set())
        for desig, info in part.pins.items():
            if desig in used:
                continue
            etype = info["electrical"]
            # NC / unconnected pins are tolerated on IO, but never on power
            if etype == 7:
                issues.append(Issue(ERROR, "PWR-FLOAT",
                                    "%s pin %s (%s) is a power pin and is not connected"
                                    % (part.ref, desig, info["name"]), part.ref))
            else:
                issues.append(Issue(WARN, "PIN-UNCONNECTED",
                                    "%s pin %s (%s) is not connected"
                                    % (part.ref, desig, info["name"]), part.ref))

    # ---- unknown pins referenced by the netlist ---------------------------
    for name in sorted(sch.nets):
        for ref, pin in sch.nets[name]:
            part = seen.get(ref)
            if part is None:
                issues.append(Issue(ERROR, "NO-PART",
                                    "net %s references unknown part %s" % (name, ref), name))
            elif pin not in part.pins:
                issues.append(Issue(ERROR, "NO-PIN",
                                    "net %s references %s.%s which does not exist"
                                    % (name, ref, pin), name))

    # ---- single ended nets -------------------------------------------------
    for name in sorted(sch.nets):
        pts = sch.nets[name]
        real = [(r, p) for r, p in pts if r in seen and p in seen[r].pins]
        if len(real) < 2 and not sch.is_power(name):
            issues.append(Issue(WARN, "NET-SINGLE",
                                "net %s connects only %d pin(s)" % (name, len(real)), name))

    # ---- drive conflicts ---------------------------------------------------
    for name in sorted(sch.nets):
        if sch.is_power(name):
            continue
        drivers, outputs = [], []
        for ref, pin in sch.nets[name]:
            part = seen.get(ref)
            if not part or pin not in part.pins:
                continue
            etype = part.pins[pin]["electrical"]
            if etype in DRIVERS:
                drivers.append("%s.%s" % (ref, pin))
            if etype == 2:
                outputs.append("%s.%s" % (ref, pin))
        if len(outputs) > 1:
            issues.append(Issue(ERROR, "MULTI-DRIVER",
                                "net %s is driven by %d outputs: %s"
                                % (name, len(outputs), ", ".join(outputs)), name))
        elif not drivers:
            # passive-only nets (crystal tanks, RC resets, resistor dividers) are
            # legitimate, so this is informational rather than a warning
            issues.append(Issue(INFO, "NO-DRIVER",
                                "net %s has no driving pin" % name, name))

    # ---- power net sanity --------------------------------------------------
    for name in sorted(sch.nets):
        if not sch.is_power(name):
            continue
        up = name.upper()
        for ref, pin in sch.nets[name]:
            part = seen.get(ref)
            if not part or pin not in part.pins:
                continue
            etype = part.pins[pin]["electrical"]
            if up.startswith("GND") or up.startswith("VSS"):
                if etype == 7 and "VCC" in part.pins[pin]["name"].upper():
                    issues.append(Issue(ERROR, "PWR-SHORT",
                                        "%s.%s (%s) looks like VCC but is tied to %s"
                                        % (ref, pin, part.pins[pin]["name"], name), name))
    return issues


def summarize(issues):
    counts = {ERROR: 0, WARN: 0, INFO: 0}
    for i in issues:
        counts[i.level] = counts.get(i.level, 0) + 1
    return counts
