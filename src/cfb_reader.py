"""Minimal OLE2 / compound-file reader (standard library only).

Enough to pull streams out of an Altium .SchLib / .SchDoc / .PcbDoc without
needing olefile.  Mirrors cfb_writer.py on the write side.
"""
import builtins
import struct

SIG = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"

TYPE_STORAGE = 1
TYPE_STREAM = 2
TYPE_ROOT = 5


class OleReader:
    def __init__(self, data):
        if data[:8] != SIG:
            raise ValueError("not an OLE2 compound file")
        self.data = data
        self.sector_size = 1 << struct.unpack_from("<H", data, 30)[0]
        self.mini_size = 1 << struct.unpack_from("<H", data, 32)[0]
        self.mini_cutoff = struct.unpack_from("<I", data, 56)[0] or 4096
        self._fat = self._read_fat()
        self._mini_fat = self._read_mini_fat()
        self.dir = self._read_dir()
        self.root = self.dir[0]
        self._mini = self._read_chain(self.root["start"], self._fat)
        self._mini = b"".join(self._sector(s) for s in self._mini)

    # -- low level -------------------------------------------------------
    def _sector(self, n):
        off = 512 + n * self.sector_size
        return self.data[off: off + self.sector_size]

    def _read_chain(self, start, fat, limit=None):
        chain = []
        seen = set()
        cur = start
        while cur < 0xFFFFFFF0:
            if cur in seen:
                break
            seen.add(cur)
            chain.append(cur)
            if limit and len(chain) >= limit:
                break
            if cur >= len(fat):
                break
            cur = fat[cur]
        return chain

    def _read_fat(self):
        (num_fat,) = struct.unpack_from("<I", self.data, 44)
        difat = list(struct.unpack_from("<109I", self.data, 76))
        # Header layout: 68 = FirstDIFATSectorLocation, 72 = NumberOfDIFATSectors.
        # Reading the pointer from 72 (was the bug) starts the walk inside a
        # FAT sector, so successive "next block" values are FAT entries and the
        # chain runs off the end of the file -- `self._sector` then returns a
        # zero-length buffer and unpack_from raises.  Libraries with <=109 FAT
        # sectors never take this branch, which is why only the large ones
        # (14-74系列TTL芯片.SchLib, 数字电路CMOS&TTL74.SCHLIB) failed.
        next_block = struct.unpack_from("<I", self.data, 68)[0]
        per_block = self.sector_size // 4 - 1        # last word is the next link
        guard = 0
        while (0 <= next_block < 0xFFFFFFF0 and len(difat) < num_fat
               and guard < 4096):
            guard += 1
            blk = self._sector(next_block)
            if len(blk) < self.sector_size:          # ran past the file
                break
            difat += list(struct.unpack_from("<%dI" % per_block, blk, 0))
            (next_block,) = struct.unpack_from("<I", blk, self.sector_size - 4)
        fat = []
        for i in range(num_fat):
            if i >= len(difat):
                break
            blk = self._sector(difat[i])
            if not blk:
                break
            fat += list(struct.unpack_from("<%dI" % (len(blk) // 4), blk, 0))
        return fat

    def _read_mini_fat(self):
        (start,) = struct.unpack_from("<I", self.data, 60)
        (count,) = struct.unpack_from("<I", self.data, 64)
        if start >= 0xFFFFFFF0 or count == 0:
            return []
        fat = []
        for s in self._read_chain(start, self._fat, count):
            blk = self._sector(s)
            fat += list(struct.unpack_from("<%dI" % (self.sector_size // 4), blk, 0))
        return fat

    # -- directory -------------------------------------------------------
    def _read_dir(self):
        (start,) = struct.unpack_from("<I", self.data, 48)
        raw = b"".join(self._sector(s) for s in self._read_chain(start, self._fat))
        entries = []
        for off in range(0, len(raw), 128):
            e = raw[off: off + 128]
            if len(e) < 128:
                break
            name_len = struct.unpack_from("<H", e, 64)[0]
            name = e[: max(0, name_len - 2)].decode("utf-16-le", "replace")
            obj_type = e[66]
            left, right, child = struct.unpack_from("<III", e, 68)
            clsid = e[80:96]
            (start_sector,) = struct.unpack_from("<I", e, 116)
            (size,) = struct.unpack_from("<Q", e, 120)
            entries.append({
                "name": name, "type": obj_type, "left": left, "right": right,
                "child": child, "clsid": clsid, "start": start_sector, "size": size,
            })
        return entries

    NO_ENTRY = 0xFFFFFFFF

    def _tree(self, prefix):
        """Iterative full traversal of the red-black directory tree.

        All three pointers must be followed -- ``left`` and ``right`` are tree
        links between siblings, ``child`` descends into a storage.  Walking only
        child+right (the obvious reading) silently drops most entries.
        Yields (node_index, path_prefix).
        """
        out = []
        stack = [(self.root.get("child", self.NO_ENTRY), prefix)]
        while stack:
            idx, pref = stack.pop()
            while idx != self.NO_ENTRY and idx < len(self.dir):
                node = self.dir[idx]
                if node["left"] != self.NO_ENTRY:
                    stack.append((node["left"], pref))
                name = node["name"]
                if node["type"] == TYPE_STORAGE:
                    if name:
                        stack.append((node["child"], pref + name + "/"))
                elif node["type"] == TYPE_STREAM and name:
                    out.append((idx, pref + name))
                idx = node["right"]
        return out

    def listdir(self):
        """Return sorted stream paths, e.g. ['FileHeader', 'AT89C51/Data']."""
        return sorted(path for _, path in self._tree(""))

    def list_storages(self):
        """Return the names of the storages directly under the root."""
        names = []
        seen = set()
        for path in self.listdir():
            if "/" in path:
                top = path.split("/")[0]
                if top not in seen:
                    seen.add(top)
                    names.append(top)
        return names

    def _index(self):
        if not hasattr(self, "_name_index"):
            self._name_index = {path: i for i, path in self._tree("")}
        return self._name_index

    def openstream(self, name):
        idx = self._index().get(name)
        if idx is None:
            raise KeyError(name)
        node = self.dir[idx]
        size = node["size"]
        if size == 0:
            return b""
        if size < self.mini_cutoff:
            data = b"".join(self._mini_sector(s) for s in self._read_chain(node["start"], self._mini_fat))
        else:
            data = b"".join(self._sector(s) for s in self._read_chain(node["start"], self._fat))
        return data[:size]

    def _mini_sector(self, n):
        off = n * self.mini_size
        return self._mini[off: off + self.mini_size]


def open_file(path):
    """Accept a filesystem path OR raw OLE2 bytes.  NB: this helper must not be
    called ``open`` -- that would shadow the builtin and every ``open(...)``
    inside this module would recurse into it."""
    if isinstance(path, (bytes, bytearray)):
        return OleReader(bytes(path))
    with builtins.open(path, "rb") as fh:
        return OleReader(fh.read())
