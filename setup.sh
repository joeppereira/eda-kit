#!/usr/bin/env bash
# eda-kit: build the real open-source analog device-model toolchain (macOS arm64).
#   ngspice (OSDI) + OpenVAF-Reloaded + BSIM-CMG 111 -> bsimcmg.osdi
# Installs into <kit>/.tools (gitignored). Idempotent.
#
# macOS gotcha handled here: Apple Silicon SIGKILLs unsigned arm64 binaries, so the
# OpenVAF binary + its dylibs are ad-hoc code-signed after download.
set -euo pipefail
KIT="$(cd "$(dirname "$0")" && pwd)"
TOOLS="$KIT/.tools"; mkdir -p "$TOOLS"

command -v ngspice >/dev/null || brew install ngspice

OV="$TOOLS/openvaf-r-v24.0.2mob-macos-aarch64"
if [ ! -x "$OV/bin/openvaf-r" ]; then
  echo "== OpenVAF =="
  curl -sL -o "$TOOLS/openvaf.tgz" \
    "https://github.com/OpenVAF/OpenVAF-Reloaded/releases/download/v24.0.2mob/openvaf-r-v24.0.2mob-macos-aarch64.tar.gz"
  tar xzf "$TOOLS/openvaf.tgz" -C "$TOOLS"
  xattr -dr com.apple.quarantine "$OV" 2>/dev/null || true
  codesign --force -s - "$OV"/lib/*.dylib "$OV/bin/openvaf-r"   # ad-hoc sign (required on arm64)
fi

echo "== BSIM-CMG 111 source + modelcards =="
RAW="https://raw.githubusercontent.com/dwarning/VA-Models/main"
VC="$TOOLS/bsimcmg/vacode111"; EX="$TOOLS/bsimcmg/examples"; mkdir -p "$VC" "$EX"
for f in bsimcmg.va bsimcmg_body.include bsimcmg_checking.include \
         bsimcmg_initialization.include bsimcmg_macros.include bsimcmg_noise.include \
         bsimcmg_parameters.include bsimcmg_variables.include constants.vams disciplines.vams; do
  curl -sL -o "$VC/$f" "$RAW/code/bsimcmg/vacode111/$f"
done
curl -sL -o "$EX/modelcard.nmos" "$RAW/examples/bsimcmg/Modelcards/modelcard.nmos"
curl -sL -o "$EX/modelcard.pmos" "$RAW/examples/bsimcmg/Modelcards/modelcard.pmos"

echo "== compile bsimcmg.va -> bsimcmg.osdi =="
( cd "$VC" && "$OV/bin/openvaf-r" bsimcmg.va )
test -f "$VC/bsimcmg.osdi" && echo "OK: $VC/bsimcmg.osdi"

echo "== GT2N 2nm GAA-nanosheet cards (BSIM-CMG v111) =="
# Refresh the vendored GT2N source cards, then translate HSPICE->OSDI for our flow.
GT="$KIT/pdk/gt2n_src"; mkdir -p "$GT"
GTRAW="https://raw.githubusercontent.com/azadnaeemi/GT2N/main/device/tt"
for vt in svt lvt ulvt; do
  curl -sfL -o "$GT/gt2_w31_${vt}_tt.sp" "$GTRAW/gt2_w31_${vt}_tt.sp" || \
    echo "  (keeping vendored gt2_w31_${vt}_tt.sp)"
done
python3 "$KIT/build_gt2n.py" "$GT" || echo "  (GT2N translate skipped)"

echo "Done. Try:  python -c 'from design_agent import migrate_cml; print(migrate_cml(\"7nm\",\"2nm\"))'"
