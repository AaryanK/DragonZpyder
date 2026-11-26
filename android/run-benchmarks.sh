#!/usr/bin/env bash
set -euo pipefail
if [ "$#" -ne 1 ]; then echo "Usage: bash android/run-benchmarks.sh <authorized physical-device-serial>"; exit 2; fi
export ANDROID_SERIAL="$1"
adb -s "$ANDROID_SERIAL" get-state | grep -qx device
for property in ro.kernel.qemu ro.boot.qemu; do
  test "$(adb -s "$ANDROID_SERIAL" shell getprop "$property" | tr -d '\r')" != 1
done
sdk="$(adb -s "$ANDROID_SERIAL" shell getprop ro.build.version.sdk | tr -d '\r')"
test "$sdk" -ge 29
cd "$(dirname "$0")"
out="device-evidence/benchmark-$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$out"
{
  echo "Commit: $(git rev-parse HEAD)"
  echo "UTC: $(date -u +%FT%TZ)"
  echo "Model: $(adb -s "$ANDROID_SERIAL" shell getprop ro.product.model | tr -d '\r')"
  echo "SDK: $sdk"
  echo "ABI: $(adb -s "$ANDROID_SERIAL" shell getprop ro.product.cpu.abi | tr -d '\r')"
  echo "Page size: $(adb -s "$ANDROID_SERIAL" shell getconf PAGE_SIZE | tr -d '\r')"
} > "$out/device.txt"
bash prepare-brand.sh
gradle --no-daemon -PdzBenchmark :benchmark:connectedBenchmarkAndroidTest
cp -R benchmark/build/outputs/connected_android_test_additional_output "$out/" 
echo "Local evidence: $out (do not publish traces from personal accounts)."
