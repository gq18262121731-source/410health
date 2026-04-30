from __future__ import annotations

import ctypes
import os
import struct
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SDK_DIR = ROOT / "摄像头说明书" / "extracted" / "SDK_phone (2)" / "SDK_phone" / "Lib" / "win32"

MACHINE_TYPES = {
    0x014C: "x86",
    0x8664: "x64",
    0x01C0: "ARM",
    0x01C4: "ARMv7",
    0xAA64: "ARM64",
}


def read_pe_imports(path: Path) -> list[str]:
    data = path.read_bytes()
    if data[:2] != b"MZ":
        return []
    pe_offset = struct.unpack_from("<I", data, 0x3C)[0]
    if data[pe_offset : pe_offset + 4] != b"PE\0\0":
        return []

    file_header = pe_offset + 4
    number_of_sections = struct.unpack_from("<H", data, file_header + 2)[0]
    optional_header_size = struct.unpack_from("<H", data, file_header + 16)[0]
    optional_header = file_header + 20
    magic = struct.unpack_from("<H", data, optional_header)[0]
    data_dir_start = optional_header + (112 if magic == 0x20B else 96)
    import_rva, _import_size = struct.unpack_from("<II", data, data_dir_start + 8)
    section_table = optional_header + optional_header_size

    sections: list[tuple[int, int, int, int]] = []
    for index in range(number_of_sections):
        offset = section_table + index * 40
        virtual_size, virtual_address, raw_size, raw_pointer = struct.unpack_from("<IIII", data, offset + 8)
        sections.append((virtual_address, max(virtual_size, raw_size), raw_pointer, raw_size))

    def rva_to_offset(rva: int) -> int | None:
        for virtual_address, virtual_size, raw_pointer, raw_size in sections:
            if virtual_address <= rva < virtual_address + virtual_size:
                delta = rva - virtual_address
                if delta >= raw_size:
                    return None
                return raw_pointer + delta
        return None

    def read_c_string(offset: int) -> str:
        end = data.find(b"\0", offset)
        if end < 0:
            return ""
        return data[offset:end].decode("ascii", errors="replace")

    imports: list[str] = []
    descriptor = rva_to_offset(import_rva)
    if descriptor is None:
        return imports

    while descriptor + 20 <= len(data):
        original_first_thunk, _time, _chain, name_rva, first_thunk = struct.unpack_from("<IIIII", data, descriptor)
        if not any((original_first_thunk, name_rva, first_thunk)):
            break
        name_offset = rva_to_offset(name_rva)
        if name_offset is not None:
            name = read_c_string(name_offset)
            if name:
                imports.append(name)
        descriptor += 20
    return imports


def read_pe_machine(path: Path) -> str:
    with path.open("rb") as file:
        if file.read(2) != b"MZ":
            return "not-pe"
        file.seek(0x3C)
        pe_offset = struct.unpack("<I", file.read(4))[0]
        file.seek(pe_offset)
        if file.read(4) != b"PE\0\0":
            return "not-pe"
        machine = struct.unpack("<H", file.read(2))[0]
    return MACHINE_TYPES.get(machine, f"unknown-0x{machine:04x}")


def try_load(path: Path) -> tuple[bool, str]:
    try:
        ctypes.WinDLL(str(path))
        return True, "loaded"
    except OSError as exc:
        return False, f"{exc.__class__.__name__}: {exc}"


def main() -> int:
    sdk_dir = Path(os.environ.get("CAMERA_SDK_DLL_DIR", str(DEFAULT_SDK_DIR)))
    print(f"Python bitness: {struct.calcsize('P') * 8}-bit")
    print(f"SDK dir: {sdk_dir}")

    if not sdk_dir.exists():
        print("SDK directory not found.")
        return 2

    dlls = [sdk_dir / "P2PAPI.dll", sdk_dir / "PPPP_API.dll"]
    any_loaded = False
    for dll in dlls:
        print(f"\nTesting {dll.name}")
        if not dll.exists():
            print("  missing")
            continue
        machine = read_pe_machine(dll)
        imports = read_pe_imports(dll)
        loaded, message = try_load(dll)
        any_loaded = any_loaded or loaded
        print(f"  arch: {machine}")
        if imports:
            print("  imports:")
            for item in imports:
                print(f"    - {item}")
        print(f"  ctypes: {message}")

    if any_loaded:
        print("\nDiagnosis: current Python can load at least one SDK DLL.")
        return 0

    print("\nDiagnosis: current Python cannot load the bundled Windows SDK DLLs.")
    print("If DLL arch is x86 and Python is 64-bit, use a 32-bit SDK gateway process or ask vendor for x64 DLLs.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
