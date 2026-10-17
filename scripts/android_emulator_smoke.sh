#!/usr/bin/env bash
set -euo pipefail

workspace="${GITHUB_WORKSPACE:-$(pwd)}"
artifact_dir="$workspace/build_mobile"
package_name="org.campusnettools.campusnetmanager"
log_file="$artifact_dir/emulator-logcat.txt"
screen_file="$artifact_dir/emulator-screen.png"
apk=""
pid=""

capture_evidence() {
  local exit_code=$?
  trap - EXIT
  mkdir -p "$artifact_dir"
  if command -v adb >/dev/null 2>&1 && adb get-state >/dev/null 2>&1; then
    pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
    if [[ -n "$pid" ]]; then
      adb logcat --pid="$pid" -d > "$log_file" 2>&1 || true
    else
      adb logcat -d -s AndroidRuntime:E python:D > "$log_file" 2>&1 || true
    fi
    adb shell screencap -p /sdcard/campusnetmanager.png >/dev/null 2>&1 \
      && adb pull /sdcard/campusnetmanager.png "$screen_file" >/dev/null 2>&1 || true
  fi
  exit "$exit_code"
}
trap capture_evidence EXIT

apk="$(find "$artifact_dir/bin" -maxdepth 1 -type f -name '*.apk' -print -quit)"
if [[ -z "$apk" ]]; then
  echo "::error::No APK found under $artifact_dir/bin"
  find "$artifact_dir" -maxdepth 3 -type f -print || true
  exit 1
fi

adb install "$apk"
adb shell monkey -p "$package_name" 1

for attempt in $(seq 1 30); do
  pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
  if [[ -n "$pid" ]]; then
    echo "CampusNetManager emulator process started: $pid"
    break
  fi
  sleep 1
done

if [[ -z "$pid" ]]; then
  echo "::error::CampusNetManager did not start in the Android emulator."
  exit 1
fi

sleep 10
adb logcat --pid="$pid" -d > "$log_file"
if grep -q 'FATAL EXCEPTION' "$log_file"; then
  echo "::error::Android emulator reported a fatal application exception."
  grep -n -A12 -B4 'FATAL EXCEPTION' "$log_file" || true
  exit 1
fi

# A live process and a few colored pixels can still be a startup screen stuck
# on "正在检测网络环境…". Wait for the network check to publish a terminal UI
# status before treating this as an app launch smoke pass.
network_status_ready=0
for attempt in $(seq 1 30); do
  adb logcat --pid="$pid" -d > "$log_file"
  if grep -q 'CNM_NETWORK_STATUS_READY:' "$log_file"; then
    network_status_ready=1
    break
  fi
  sleep 1
done
if [[ "$network_status_ready" -ne 1 ]]; then
  echo "::error::Android UI stayed on its initial network-check status."
  tail -n 80 "$log_file" || true
  exit 1
fi
grep 'CNM_NETWORK_STATUS_READY:' "$log_file" | tail -1

pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
if [[ -z "$pid" ]]; then
  echo "::error::CampusNetManager exited during the emulator smoke period."
  exit 1
fi

for attempt in $(seq 1 10); do
  adb shell screencap -p /sdcard/campusnetmanager.png
  adb pull /sdcard/campusnetmanager.png "$screen_file"
  if python "$workspace/scripts/check_android_screenshot.py" "$screen_file"; then
    exit 0
  fi
  sleep 2
done
echo "::error::Android app stayed alive but never rendered visible UI content."
exit 1
