#!/bin/bash
# Configure and build ACTS (Fatras + ODD + DD4hep + Pythia8 + Python
# bindings) on a Purdue Analysis Facility session. Run setup_env.sh once
# first. See README.md for why each step below is needed.
set -ex

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/../../../.." && pwd)"
STATE="$ROOT/.purdue-af"
BUILD="$ROOT/build"
LCG_VIEW=/cvmfs/sft.cern.ch/lcg/views/LCG_107/x86_64-el8-gcc11-opt

export CCACHE_DIR="${CCACHE_DIR:-$STATE/ccache}"
mkdir -p "$CCACHE_DIR"

source "$LCG_VIEW/setup.sh"

# LCG_107's own gcc11 does not support std::format (needed by ACTS, requires
# GCC >= 13 both at compile time and in libstdc++ at runtime). Use a modern
# GCC from a dedicated pixi env as the compiler frontend while keeping every
# other dependency (Boost, ROOT, DD4hep, Geant4, Pythia8, Qt5, ...) from the
# LCG view. The conda-forge g++ wrapper bakes in an RPATH to its own newer
# libstdc++, so binaries pick the right runtime automatically. It also
# supplies X11/OpenGL dev headers (missing from this container) needed to
# satisfy DD4hep's Geant4Config.cmake, which unconditionally requires X11/Qt5.
GCCENV="$STATE/gccenv/.pixi/envs/default"
export CC="$GCCENV/bin/x86_64-conda-linux-gnu-gcc"
export CXX="$GCCENV/bin/x86_64-conda-linux-gnu-g++"
export CMAKE_PREFIX_PATH="$CMAKE_PREFIX_PATH:$GCCENV"

# DD4hep's plugin-component-listing build step dlopens the just-built
# libOpenDataDetector.so (linked against our newer libstdc++ via rpath)
# from inside a *preexisting* LCG-provided helper binary that is itself
# linked against the older gcc11 libstdc++. Because both share the SONAME
# libstdc++.so.6, whichever copy the process loads first wins for the whole
# process -- and that helper binary's own rpath/LD_LIBRARY_PATH favors the
# older one, so our newer symbols (e.g. GLIBCXX_3.4.31) go missing. Put the
# newer libstdc++ first on LD_LIBRARY_PATH so it wins the race instead; it is
# a strict superset of the older one so this is safe for the LCG libraries.
export LD_LIBRARY_PATH="$GCCENV/lib:$LD_LIBRARY_PATH"

# Our compiler's --sysroot is self-contained (conda-forge's portability
# sysroot) and does not fall back to the host's /usr/include, so dev headers
# that normally ship as "-devel" system packages (bzlib.h, zlib.h, X11, GL)
# have to come from here explicitly even when a same-named runtime .so
# already exists on the host.
export CPATH="$GCCENV/include:$CPATH"

# Same sysroot isolation bites at link time: our linker won't search the
# host's /usr/lib64 by default, so it can't locate libssl.so.1.1/liblzma.so.5
# that ROOT's libNet.so/libCore.so (from the LCG view) need to resolve their
# own undefined symbols against ("libssl.so.1.1 ... not found" at link time,
# even though it's present and would resolve fine at runtime via the default
# loader path). -rpath-link just tells the *linker* where to look; it does
# not get embedded as a runtime search path. conda's own openssl is 3.x and
# wouldn't provide the OPENSSL_1_1_0 symbol versions needed here anyway.
RPATH_LINK_FLAG="-Wl,-rpath-link,/usr/lib64"

# pybind11's bundled legacy FindPythonLibsNew.cmake ignores the Python we
# already resolved via FindPython and probes "/bin/python" (system python)
# instead, under an environment whose PYTHONHOME/PYTHONPATH were set up by
# the LCG view's setup.sh for ITS python3.11 -- that mismatch breaks the
# system python's stdlib discovery ("No module named 'encodings'"). Force it
# onto the LCG view's own python3.11 explicitly.
PYTHON_EXE=$(command -v python3.11)

python3 "$HERE/patch_geant4_cmake.py" "$LCG_VIEW" "$STATE/patched-cmake/Geant4"

cmake -B "$BUILD" -S "$ROOT" -GNinja \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_CXX_STANDARD=20 \
    -DCMAKE_C_COMPILER="$CC" \
    -DCMAKE_CXX_COMPILER="$CXX" \
    -DCMAKE_CXX_COMPILER_LAUNCHER=ccache \
    -DGeant4_DIR="$STATE/patched-cmake/Geant4" \
    -DPYTHON_EXECUTABLE="$PYTHON_EXE" \
    -DCMAKE_EXE_LINKER_FLAGS="$RPATH_LINK_FLAG" \
    -DCMAKE_SHARED_LINKER_FLAGS="$RPATH_LINK_FLAG" \
    -DCMAKE_MODULE_LINKER_FLAGS="$RPATH_LINK_FLAG" \
    -DACTS_ENABLE_LOG_FAILURE_THRESHOLD=OFF \
    -DACTS_BUILD_FATRAS=ON \
    -DACTS_BUILD_ODD=ON \
    -DACTS_BUILD_PLUGIN_DD4HEP=ON \
    -DACTS_BUILD_EXAMPLES_DD4HEP=ON \
    -DACTS_BUILD_EXAMPLES_PYTHON_BINDINGS=ON \
    -DACTS_BUILD_EXAMPLES_ROOT=ON \
    -DACTS_BUILD_EXAMPLES_PYTHIA8=ON \
    -DACTS_BUILD_PLUGIN_JSON=ON \
    -DACTS_BUILD_UNITTESTS=OFF \
    -DACTS_BUILD_INTEGRATIONTESTS=OFF \
    -DACTS_BUILD_EXAMPLES_UNITTESTS=OFF \
    -DACTS_BUILD_BENCHMARKS=OFF

cmake --build "$BUILD" -- -j"${BUILD_JOBS:-64}"

echo "Build complete. Source $BUILD/python/setup.sh and $BUILD/thirdparty/OpenDataDetector/this_odd.sh to use it."
