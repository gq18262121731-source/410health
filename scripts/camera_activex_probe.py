from __future__ import annotations

import argparse
import platform
import sys


DEFAULT_CLSID = "1E125331-B4E3-4EE3-B3C1-24AD1A3E5DEB"


def probe_activex(clsid: str) -> int:
    normalized = clsid.strip().strip("{}")
    print(f"Python: {sys.executable}")
    print(f"Python bitness: {platform.architecture()[0]}")
    print(f"ActiveX CLSID: {{{normalized}}}")

    try:
        import winreg
    except ImportError:
        print("Result: ActiveX probing is only available on Windows.")
        return 2

    registry_path = f"CLSID\\{{{normalized}}}\\InprocServer32"
    views = [
        ("64-bit registry view", getattr(winreg, "KEY_WOW64_64KEY", 0)),
        ("32-bit registry view", getattr(winreg, "KEY_WOW64_32KEY", 0)),
        ("default registry view", 0),
    ]

    found = False
    for label, view_flag in views:
        try:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT, registry_path, 0, winreg.KEY_READ | view_flag) as key:
                dll_path, _value_type = winreg.QueryValueEx(key, "")
                print(f"{label}: registered")
                print(f"  InprocServer32: {dll_path}")
                found = True
        except OSError as exc:
            print(f"{label}: not registered ({exc})")

    if found:
        print("\nDiagnosis: ActiveX is registered on this machine.")
        print("Next: build a small local bridge process if we choose the ActiveX route.")
        return 0

    print("\nDiagnosis: ActiveX is not registered.")
    print("Next: install/register WEB-SDK ActiveX only on the trusted Windows backend machine, not in the browser.")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Probe the vendor WEB-SDK ActiveX registration.")
    parser.add_argument("--clsid", default=DEFAULT_CLSID)
    args = parser.parse_args()
    return probe_activex(args.clsid)


if __name__ == "__main__":
    raise SystemExit(main())
