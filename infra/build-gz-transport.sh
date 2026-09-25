#!/usr/bin/env bash
# Build gz-transport 15.1.0 with infra/patches/gz-transport15-zenoh-fixes.patch
# and swap it into a conda env, keeping the conda original as *.orig.
#
#   infra/build-gz-transport.sh            build and install into ENV_DIR
#   infra/build-gz-transport.sh --revert   put the conda original back
#
# ENV_DIR defaults to this repo's pixi env (macOS, for the native gz GUI); the
# world and px4 images pass their own env. Dependencies are pinned to the
# versions installed in ENV_DIR (read from conda-meta), so the library matches
# what gz-sim, gz-gui and PX4 there were built with. Needs pixi and network.
set -euo pipefail

HERE=$(cd "$(dirname "$0")" && pwd)
ENV_DIR=${ENV_DIR:-$HERE/../.pixi/envs/default}
META=$ENV_DIR/conda-meta
if [ "$(uname)" = Darwin ]; then LIB=libgz-transport.15.1.0.dylib; else LIB=libgz-transport.so.15.1.0; fi
TARGET=$ENV_DIR/lib/$LIB

if [ "${1:-}" = "--revert" ]; then
	[ -f "$TARGET.orig" ] || { echo "no $LIB.orig: nothing to revert"; exit 1; }
	mv "$TARGET.orig" "$TARGET"
	echo "restored the conda $LIB"
	exit 0
fi

compgen -G "$META/libgz-transport-15.1.0-*.json" >/dev/null ||
	{ echo "$ENV_DIR does not have gz-transport 15.1.0; the patch is made for it"; exit 1; }

# version of an installed conda package, e.g. ver libprotobuf -> 7.35.1
ver() { ls "$META" | sed -n "s/^$1-\([0-9][^-]*\)-.*\.json$/\1/p"; }

# Build-time packages pinned to the runtime library installed next to them
# (build tools like protoc or gz-msgs' metapackage need not be in ENV_DIR).
specs=(git cmake ninja cxx-compiler pkg-config cppzmq)
for pin in libgz-cmake:libgz-cmake libgz-msgs:libgz-msgs gz-msgs:libgz-msgs \
	libgz-utils:libgz-utils libgz-tools:libgz-tools libprotobuf:libprotobuf \
	protobuf:libprotobuf libabseil:libabseil zeromq:zeromq libsqlite:libsqlite \
	libzenohc:libzenohc libzenohcxx:libzenohc; do  # zenoh-cpp is header-only, must match zenoh-c
	v=$(ver "${pin#*:}")
	[ -n "$v" ] || { echo "${pin#*:} is not installed in $ENV_DIR"; exit 1; }
	specs+=("${pin%%:*}=$v")
done
args=(); for s in "${specs[@]}"; do args+=(--spec "$s"); done

# The conda original is the reference until the first install.
REF=$TARGET.orig; [ -f "$REF" ] || REF=$TARGET
WORK=${TMPDIR:-/tmp}/gz-transport-build
rm -rf "$WORK"

pixi exec -c https://prefix.dev/conda-forge "${args[@]}" -- bash -euo pipefail -c '
	git clone -q --depth 1 --branch gz-transport15_15.1.0 \
		https://github.com/gazebosim/gz-transport.git "$1"
	git -C "$1" apply "$2"
	cmake -S "$1" -B "$1/build" -G Ninja -DCMAKE_BUILD_TYPE=Release \
		-DCMAKE_PREFIX_PATH="$CONDA_PREFIX" -DBUILD_TESTING=OFF -DSKIP_PYBIND11=ON >/dev/null
	cmake --build "$1/build" --target gz-transport >/dev/null
	# Nothing the prebuilt gz binaries link against may go missing.
	if [ "$(uname)" = Darwin ]; then syms() { "${NM:-nm}" -gU "$1" | awk "{print \$3}" | sort; }
	else syms() { "${NM:-nm}" -D --defined-only "$1" | awk "{print \$3}" | grep -vxE "_init|_fini" | sort; }; fi  # ELF init/fini, not API
	missing=$(comm -23 <(syms "$3") <(syms "$1/build/lib/$4"))
	if [ -n "$missing" ]; then
		echo "patched library lacks exported symbols:"; echo "$missing" | c++filt; exit 1
	fi
' _ "$WORK" "$HERE/patches/gz-transport15-zenoh-fixes.patch" "$REF" "$LIB"

[ -f "$TARGET.orig" ] || cp -p "$TARGET" "$TARGET.orig"
cp "$WORK/build/lib/$LIB" "$TARGET"
rm -rf "$WORK"
echo "installed the patched $LIB into $ENV_DIR (conda original kept as $LIB.orig)"
