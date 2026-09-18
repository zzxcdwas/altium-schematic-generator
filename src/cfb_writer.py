"""Minimal OLE2 / compound file writer, standard library only.

Altium's native .SchDoc is an OLE compound document whose "FileHeader" stream holds
the schematic records. AD refuses to open the plain-text ASCII flavour, so we build
the real container ourselves:

  header (512B) | big stream sectors | mini stream sectors | miniFAT | directory | FAT

Streams under 4096 bytes live in the mini stream, chained through the miniFAT, exactly
as the spec requires.
"""
import struct
import tempfile

SECTOR = 512
MINI_SECTOR = 64
CUTOFF = 4096
ENDOFCHAIN = 0xFFFFFFFE
FREESECT = 0xFFFFFFFF
FATSECT = 0xFFFFFFFD
NOSTREAM = 0xFFFFFFFF
ENTRY = 128


def _ceil_div(a, b):
    return (a + b - 1) // b


class OleWriter:
    def __init__(self):
        self.streams = []

    def add(self, name, data):
        self.streams.append((name, data))
        return self

    # ------------------------------------------------------------------
    def build(self):
        big = []
        small = []
        for name, data in self.streams:
            (big if len(data) >= CUTOFF else small).append([name, data])

        # ---- mini stream: pack the small streams into 64 byte slots ----
        mini_data = bytearray()
        mini_fat = []
        small_info = []          # (name, start_mini_sector, size)
        for name, data in small:
            count = max(1, _ceil_div(len(data), MINI_SECTOR))
            start = len(mini_data) // MINI_SECTOR
            padded = data + b"\x00" * (count * MINI_SECTOR - len(data))
            mini_data += padded
            for i in range(count):
                mini_fat.append(start + i + 1 if i < count - 1 else ENDOFCHAIN)
            small_info.append((name, start, len(data)))

        # ---- big stream layout ----
        big_info = []            # (name, start_sector, size)
        sector = 0
        for name, data in big:
            count = _ceil_div(len(data), SECTOR)
            big_info.append((name, sector, len(data), count))
            sector += count
        big_sectors = sector

        mini_start = big_sectors
        mini_sector_count = _ceil_div(len(mini_data), SECTOR)
        mini_start = mini_start if mini_sector_count else ENDOFCHAIN
        cursor = big_sectors + mini_sector_count

        mini_fat_sector_count = _ceil_div(len(mini_fat) * 4, SECTOR)
        mini_fat_start = cursor if mini_fat_sector_count else ENDOFCHAIN
        cursor += mini_fat_sector_count

        entry_count = 1 + len(self.streams)          # root + one per stream
        dir_sector_count = _ceil_div(entry_count * ENTRY, SECTOR)
        dir_start = cursor
        cursor += dir_sector_count

        fixed = cursor
        fat_sector_count = 1
        while True:
            total = fixed + fat_sector_count
            need = _ceil_div(total, SECTOR // 4)
            if need <= fat_sector_count:
                break
            fat_sector_count = need
        fat_start = fixed

        # ---- FAT ----
        fat = [FREESECT] * (fat_sector_count * (SECTOR // 4))

        def chain(target, start, count):
            for i in range(count):
                target[start + i] = start + i + 1 if i < count - 1 else ENDOFCHAIN

        for name, start, size, count in big_info:
            chain(fat, start, count)
        if mini_sector_count:
            chain(fat, big_sectors, mini_sector_count)
        for i in range(mini_fat_sector_count):
            chain(fat, mini_fat_start, mini_fat_sector_count)
        for i in range(dir_sector_count):
            chain(fat, dir_start, dir_sector_count)
        for i in range(fat_sector_count):
            fat[fat_start + i] = FATSECT

        # ---- directory ----
        # children must be ordered by name length then case-insensitive name, and the
        # root's child pointer has to point at the first entry of that order
        order = sorted(range(len(self.streams)),
                       key=lambda i: (len(self.streams[i][0]), self.streams[i][0].upper()))
        position = {idx: pos for pos, idx in enumerate(order)}
        root_child = order[0] + 1 if order else NOSTREAM

        entries = []
        entries.append(self._entry("Root Entry", 5, mini_start if mini_sector_count else ENDOFCHAIN,
                                   len(mini_data), child=root_child))
        for idx, (name, data) in enumerate(self.streams):
            pos = position[idx]
            right = order[pos + 1] + 1 if pos + 1 < len(order) else NOSTREAM
            if len(data) >= CUTOFF:
                for bname, start, size, count in big_info:
                    if bname == name:
                        entries.append(self._entry(name, 2, start, size, right=right))
                        break
            else:
                for sname, start, size in small_info:
                    if sname == name:
                        entries.append(self._entry(name, 2, start, size, right=right))
                        break

        dir_data = bytearray()
        for e in entries:
            dir_data += e
        dir_data += b"\x00" * (dir_sector_count * SECTOR - len(dir_data))

        # ---- assemble ----
        output = bytearray()
        output += self._header(fat_sector_count, dir_start, mini_fat_start,
                               mini_fat_sector_count, fat_start, fat_sector_count)

        for name, data in big:
            count = _ceil_div(len(data), SECTOR)
            output += data + b"\x00" * (count * SECTOR - len(data))

        output += bytes(mini_data)
        output += b"\x00" * (mini_sector_count * SECTOR - len(mini_data))

        mf = b"".join(struct.pack("<I", v) for v in mini_fat)
        output += mf + b"\x00" * (mini_fat_sector_count * SECTOR - len(mf))
        output += dir_data
        fat_bytes = b"".join(struct.pack("<I", v) for v in fat)
        output += fat_bytes
        return bytes(output)

    # ------------------------------------------------------------------
    @staticmethod
    def _entry(name, obj_type, start, size, child=NOSTREAM, right=NOSTREAM, left=NOSTREAM):
        encoded = name.encode("utf-16-le") + b"\x00\x00"
        if len(encoded) > 64:
            raise ValueError("stream name too long: " + name)
        entry = bytearray(ENTRY)
        entry[0:len(encoded)] = encoded
        struct.pack_into("<H", entry, 64, len(encoded))
        entry[66] = obj_type
        entry[67] = 1                                   # colour: black
        struct.pack_into("<I", entry, 68, left)
        struct.pack_into("<I", entry, 72, right)
        struct.pack_into("<I", entry, 76, child)
        struct.pack_into("<I", entry, 116, start)
        struct.pack_into("<Q", entry, 120, size)
        return bytes(entry)

    @staticmethod
    def _header(fat_count, dir_start, mini_fat_start, mini_fat_count, fat_start, fat_sector_count):
        header = bytearray(SECTOR)
        header[0:8] = b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"
        struct.pack_into("<HH", header, 24, 0x003E, 0x0003)      # minor, major version
        struct.pack_into("<H", header, 28, 0xFFFE)               # little endian
        struct.pack_into("<H", header, 30, 9)                    # sector shift 512
        struct.pack_into("<H", header, 32, 6)                    # mini sector shift 64
        struct.pack_into("<I", header, 40, 0)                    # number of dir sectors (v3: 0)
        struct.pack_into("<I", header, 44, fat_sector_count)
        struct.pack_into("<I", header, 48, dir_start)
        struct.pack_into("<I", header, 52, 0)                    # transaction signature
        struct.pack_into("<I", header, 56, CUTOFF)
        struct.pack_into("<I", header, 60, mini_fat_start)
        struct.pack_into("<I", header, 64, mini_fat_count)
        struct.pack_into("<I", header, 68, ENDOFCHAIN)           # first DIFAT sector
        struct.pack_into("<I", header, 72, 0)                    # number of DIFAT sectors
        difat = [FREESECT] * 109
        for i in range(fat_sector_count):
            difat[i] = fat_start + i
        struct.pack_into("<109I", header, 76, *difat)
        return bytes(header)


if __name__ == "__main__":
    w = OleWriter()
    w.add("FileHeader", b"|HEADER=Protel for Windows - Schematic Capture Ascii File Version 5.0|WEIGHT=0\x00")
    w.add("Storage", b"|HEADER=Icon storage|WEIGHT=0\x00")
    data = w.build()
    path = os.path.join(tempfile.gettempdir(), "ole_smoke.ole")
    open(path, "wb").write(data)
    print("wrote", path, len(data))
