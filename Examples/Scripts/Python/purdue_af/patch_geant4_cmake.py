#!/usr/bin/env python3
"""Build a local, patched copy of the LCG view's Geant4 CMake config.

DD4hep built against Geant4 (true of the LCG releases on CVMFS) makes
find_package(DD4hep) transitively require Geant4's full visualization stack
(X11, OpenGL, Qt5, Motif, ...) via Geant4Config.cmake's find_dependency()
calls -- even though nothing in this build uses Geant4 visualization. X11,
OpenGL and Qt5 are easy to satisfy (conda-forge packages / already in the
LCG view), but Motif/OpenMotif has no conda-forge package and nothing else
provides it here. This script copies the view's lib64/cmake/Geant4
directory out to a writable location and flips just the one flag that
drags Motif in, then fixes up the two files whose logic locates the real
LCG install *relative to their own file location* (true in the view, false
once copied elsewhere) to point at the real prefix directly instead.

Usage: patch_geant4_cmake.py <lcg_view_dir> <output_dir>
Then pass -DGeant4_DIR=<output_dir> to ACTS's cmake configure.
"""
import pathlib
import shutil
import sys


def replace_or_die(path: pathlib.Path, old: str, new: str) -> None:
    text = path.read_text()
    if old not in text:
        sys.exit(
            f"error: expected text not found in {path}\n"
            "The LCG Geant4 CMake config has likely changed shape; this "
            "script needs to be updated to match. Expected:\n" + old
        )
    path.write_text(text.replace(old, new))


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(f"usage: {sys.argv[0]} <lcg_view_dir> <output_dir>")
    lcg_view = pathlib.Path(sys.argv[1]).resolve()
    out_dir = pathlib.Path(sys.argv[2]).resolve()

    src = lcg_view / "lib64" / "cmake" / "Geant4"
    if not src.is_dir():
        sys.exit(f"error: {src} does not exist")

    if out_dir.exists():
        shutil.rmtree(out_dir)
    # follow_symlinks: the view's cmake dir is a tree of symlinks into
    # /cvmfs/sft.cern.ch/lcg/releases/..., which get rewritten below to
    # point at the view itself, not the copy -- dereference them into real
    # files first so they're actually writable.
    shutil.copytree(src, out_dir, symlinks=False)

    replace_or_die(
        out_dir / "Geant4Config.cmake",
        "set(Geant4_motif_FOUND ON)",
        "set(Geant4_motif_FOUND OFF)",
    )

    # PTLConfig.cmake, PTLTargets.cmake and Geant4LibraryDepends.cmake each
    # compute their real prefix as a fixed number of parent directories
    # above their own file location -- correct inside the view, wrong once
    # copied out. Hardcode the real view path instead.
    replace_or_die(
        out_dir / "PTL" / "PTLConfig.cmake",
        'get_filename_component(PACKAGE_PREFIX_DIR "${CMAKE_CURRENT_LIST_DIR}/../../../../" ABSOLUTE)',
        f'set(PACKAGE_PREFIX_DIR "{lcg_view}")',
    )
    for rel, up_count in [
        ("PTL/PTLTargets.cmake", 4),
        ("Geant4LibraryDepends.cmake", 3),
    ]:
        gets = "\n".join(
            ['get_filename_component(_IMPORT_PREFIX "${CMAKE_CURRENT_LIST_FILE}" PATH)']
            + ['get_filename_component(_IMPORT_PREFIX "${_IMPORT_PREFIX}" PATH)'] * up_count
        )
        replace_or_die(
            out_dir / rel,
            f"# Compute the installation prefix relative to this file.\n{gets}",
            f'set(_IMPORT_PREFIX "{lcg_view}")',
        )

    print(f"Patched Geant4 CMake config written to {out_dir}")


if __name__ == "__main__":
    main()
