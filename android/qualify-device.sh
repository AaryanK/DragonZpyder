#!/usr/bin/env bash
set -euo pipefail
# Run with a real, authorized USB/ADB device. No test accounts or secrets are created.
if [ "$#" -ne 2 ]; then echo "Usage: bash android/qualify-device.sh <device-serial> <signed-or-debug-apk>"; exit 2; fi
serial="$1"; apk="$2"
test -f "$apk"
adb -s "$serial" get-state | grep -qx device
test "$(adb -s "$serial" shell getprop ro.kernel.qemu | tr -d '\r')" != "1"
test "$(adb -s "$serial" shell getprop ro.boot.qemu | tr -d '\r')" != "1"
out="android/device-evidence/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
sha256sum "$apk" > "$out/apk-sha256.txt"
{
  echo "UTC: $(date -u +%FT%TZ)"
  echo "Manufacturer: $(adb -s "$serial" shell getprop ro.product.manufacturer)"
  echo "Model: $(adb -s "$serial" shell getprop ro.product.model)"
  echo "SDK: $(adb -s "$serial" shell getprop ro.build.version.sdk)"
  echo "ABI: $(adb -s "$serial" shell getprop ro.product.cpu.abi)"
  echo "Page size: $(adb -s "$serial" shell getconf PAGE_SIZE)"
} > "$out/device.txt"
adb -s "$serial" install -r "$apk" | tee "$out/install.txt"
adb -s "$serial" shell am start -W -n xyz.dragonzpyder.android/.MainActivity | tee "$out/launch.txt"
echo "Install and launch evidence only. Complete the manual qualification matrix in RELEASE_GATES.md."
echo "Never upload logcat dumps, account screens, or private messages to a public repository."
