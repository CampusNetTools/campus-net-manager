#!/usr/bin/env bash
set -euo pipefail

workspace="${GITHUB_WORKSPACE:-$(pwd)}"
artifact_dir="$workspace/build_mobile"
package_name="org.campusnettools.campusnetmanager"
log_file="$artifact_dir/emulator-logcat.txt"
screen_file="$artifact_dir/emulator-screen.png"
probe_enabled="${RUN_EMULATOR_ACCEPTANCE_PROBE:-false}"
fixture_file="$workspace/scripts/android_emulator_profile_fixture.json"
apk=""
pid=""
original_wifi=""
wifi_changed=0
probe_started=0
probe_file_local="$artifact_dir/emulator-profile.enc"
probe_relative_path=""

find_probe_profile() {
  probe_relative_path="$(adb shell run-as "$package_name" sh -c \
    'find files -name profile.enc -type f -print -quit' 2>/dev/null | tr -d '\r')"
  if [[ "$probe_relative_path" != "files/profile.enc" && \
        "$probe_relative_path" != "files/app/profile.enc" ]]; then
    echo "::error::Android encrypted profile was not found in the expected private app directory."
    return 1
  fi
}

append_app_log() {
  local app_pid="$1"
  adb logcat --pid="$app_pid" -d 2>/dev/null \
    | grep -E 'CNM_|FATAL EXCEPTION|AndroidRuntime' >> "$log_file" || true
}

restore_emulator_wifi() {
  if [[ "$wifi_changed" -eq 1 && -n "$original_wifi" ]]; then
    if [[ "$original_wifi" == "1" ]]; then
      adb shell svc wifi enable >/dev/null 2>&1 || true
    else
      adb shell svc wifi disable >/dev/null 2>&1 || true
    fi
    wifi_changed=0
  fi
}

assert_wifi_state() {
  local expected="$1"
  local actual
  actual="$(adb shell settings get global wifi_on 2>/dev/null | tr -d '\r')"
  if [[ "$actual" != "$expected" ]]; then
    echo "::error::Android emulator Wi-Fi state did not reach expected value $expected."
    return 1
  fi
  echo "CNM_ANDROID_WIFI_STATE_VERIFIED=$actual" >> "$log_file"
}

capture_evidence() {
  local exit_code=$?
  trap - EXIT
  mkdir -p "$artifact_dir"
  if command -v adb >/dev/null 2>&1 && adb get-state >/dev/null 2>&1; then
    pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
    if [[ -n "$pid" ]]; then
      append_app_log "$pid"
      adb shell screencap -p /sdcard/campusnetmanager.png >/dev/null 2>&1 \
        && adb pull /sdcard/campusnetmanager.png "$screen_file" >/dev/null 2>&1 || true
    fi
    if [[ "$probe_enabled" == "true" && "$probe_started" -eq 1 ]]; then
      # Capture only the synthetic ciphertext so the runner can check the file
      # format without printing or uploading a plaintext fixture.
      if [[ -n "$probe_relative_path" ]]; then
        adb exec-out run-as "$package_name" cat "$probe_relative_path" \
        > "$probe_file_local" 2>/dev/null || true
      fi
      adb shell pm clear "$package_name" >/dev/null 2>&1 || true
      echo "CNM_ANDROID_ACCEPTANCE_DATA_CLEARED" >> "$log_file"
    fi
  fi
  restore_emulator_wifi
  exit "$exit_code"
}
trap capture_evidence EXIT

mkdir -p "$artifact_dir"
: > "$log_file"
apk="$(find "$artifact_dir/bin" -maxdepth 1 -type f -name '*.apk' -print -quit)"
if [[ -z "$apk" ]]; then
  echo "::error::No APK found under $artifact_dir/bin"
  find "$artifact_dir" -maxdepth 3 -type f -print || true
  exit 1
fi

adb uninstall "$package_name" >/dev/null 2>&1 || true
adb install "$apk"

if [[ "$probe_enabled" == "true" ]]; then
  if [[ ! -f "$fixture_file" ]]; then
    echo "::error::The synthetic Android profile fixture is missing."
    exit 1
  fi
  # This is a debuggable hosted emulator install. Keep the JSON outside the APK
  # and place it only in the app-private user_data_dir via run-as.
  adb shell run-as "$package_name" mkdir -p files/app
  adb shell run-as "$package_name" tee files/app/acceptance-profile.json \
    < "$fixture_file" >/dev/null
  adb shell run-as "$package_name" tee files/acceptance-profile.json \
    < "$fixture_file" >/dev/null
  adb shell pm grant "$package_name" android.permission.POST_NOTIFICATIONS
  original_wifi="$(adb shell settings get global wifi_on 2>/dev/null | tr -d '\r')"
  if [[ "$original_wifi" != "0" && "$original_wifi" != "1" ]]; then
    echo "::error::Could not read the emulator's original Wi-Fi state."
    exit 1
  fi
  probe_started=1
  echo "CNM_ANDROID_WIFI_ORIGINAL=$original_wifi" >> "$log_file"
fi

launch_app() {
  adb shell monkey -p "$package_name" 1 >/dev/null
  local found_pid=""
  for attempt in $(seq 1 30); do
    found_pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
    if [[ -n "$found_pid" ]]; then
      echo "CampusNetManager emulator process started: $found_pid"
      pid="$found_pid"
      return 0
    fi
    sleep 1
  done
  echo "::error::CampusNetManager did not start in the Android emulator."
  return 1
}

wait_for_marker() {
  local marker="$1"
  local app_pid="$2"
  for attempt in $(seq 1 30); do
    append_app_log "$app_pid"
    if grep -Fq "$marker" "$log_file"; then
      grep -F "$marker" "$log_file" | tail -1
      return 0
    fi
    if grep -q 'FATAL EXCEPTION' "$log_file"; then
      echo "::error::Android emulator reported a fatal application exception."
      tail -n 80 "$log_file" || true
      return 1
    fi
    sleep 1
  done
  echo "::error::Timed out waiting for Android acceptance marker: $marker"
  tail -n 80 "$log_file" || true
  return 1
}

assert_service_running() {
  local description="$1"
  local services=""
  for attempt in $(seq 1 30); do
    services="$(adb shell dumpsys activity services "$package_name" 2>/dev/null | tr -d '\r')"
    if grep -Fq 'ServiceCampusguard' <<< "$services" && \
       grep -Eq 'isForeground=true|foregroundId=[1-9][0-9]*' <<< "$services"; then
      echo "CNM_ANDROID_FOREGROUND_SERVICE_PRESENT $description" >> "$log_file"
      return 0
    fi
    sleep 1
  done
  echo "::error::Android foreground service did not reach foreground state $description."
  grep -E 'ServiceCampusguard|isForeground=|foregroundId=|foregroundServiceType=|startRequested=' \
    <<< "$services" | tee -a "$log_file" >&2 || true
  return 1
}

launch_app
if [[ "$probe_enabled" == "true" ]]; then
  wait_for_marker "CNM_ANDROID_PROFILE_STORE_WRITE_PASS" "$pid"
  wait_for_marker "CNM_ANDROID_FOREGROUND_SERVICE_START_REQUESTED" "$pid"
  wait_for_marker "CNM_NETWORK_STATUS_READY:" "$pid"
  assert_service_running "after first start"
  find_probe_profile
  adb exec-out run-as "$package_name" cat "$probe_relative_path" > "$probe_file_local"
  python - "$probe_file_local" <<'PY'
import pathlib
import sys

payload = pathlib.Path(sys.argv[1]).read_bytes()
if not payload.startswith(b"v1:"):
    raise SystemExit("::error::Android acceptance profile is not encrypted with the v1 format.")
if b"synthetic-keystore-round-trip-not-a-secret" in payload or b"127.0.0.1" in payload:
    raise SystemExit("::error::Android profile ciphertext contains its plaintext test fixture.")
print("CNM_ANDROID_PROFILE_CIPHERTEXT_CHECK_PASS")
PY

  # Stop the app process, not the Android system. The encrypted profile and
  # non-exportable Keystore key must survive this process restart.
  adb shell am force-stop "$package_name"
  launch_app
  wait_for_marker "CNM_ANDROID_PROFILE_STORE_RESTART_PASS" "$pid"
  find_probe_profile
  wait_for_marker "CNM_ANDROID_FOREGROUND_SERVICE_START_REQUESTED" "$pid"
  wait_for_marker "CNM_NETWORK_STATUS_READY:" "$pid"
  assert_service_running "after process restart"

  original_wifi="$(adb shell settings get global wifi_on 2>/dev/null | tr -d '\r')"
  if [[ "$original_wifi" == "1" ]]; then
    adb shell svc wifi disable
    wifi_changed=1
    echo "CNM_ANDROID_WIFI_CHANGED=disabled" >> "$log_file"
    sleep 5
    assert_wifi_state 0
    adb shell svc wifi enable
    sleep 5
    assert_wifi_state 1
  else
    adb shell svc wifi enable
    wifi_changed=1
    echo "CNM_ANDROID_WIFI_CHANGED=enabled" >> "$log_file"
    sleep 5
    assert_wifi_state 1
    adb shell svc wifi disable
    sleep 5
    assert_wifi_state 0
  fi
  restore_emulator_wifi
  assert_wifi_state "$original_wifi"
  echo "CNM_ANDROID_WIFI_RESTORED=$original_wifi" >> "$log_file"
  pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
  if [[ -z "$pid" ]]; then
    echo "::error::Android app exited during the emulator Wi-Fi state change."
    exit 1
  fi
  append_app_log "$pid"
  if grep -q 'FATAL EXCEPTION' "$log_file"; then
    echo "::error::Android emulator reported a fatal exception after Wi-Fi state change."
    tail -n 80 "$log_file" || true
    exit 1
  fi
  assert_service_running "after emulator Wi-Fi state changes"
  echo "CNM_ANDROID_PROCESS_SURVIVED_EMULATOR_WIFI_CHANGE"

  # Remove all synthetic Android Keystore/app-private state before capturing the
  # ordinary startup screenshot. EXIT cleanup repeats this if a command fails.
  adb shell am force-stop "$package_name"
  adb shell pm clear "$package_name" >/dev/null
  probe_started=0
  rm -f "$probe_file_local"
  echo "CNM_ANDROID_ACCEPTANCE_DATA_CLEARED" >> "$log_file"
  launch_app
fi

network_status_ready=0
for attempt in $(seq 1 30); do
  append_app_log "$pid"
  if grep -Fq 'CNM_NETWORK_STATUS_READY:' "$log_file"; then
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
grep -F 'CNM_NETWORK_STATUS_READY:' "$log_file" | tail -1

sleep 10
pid="$(adb shell pidof "$package_name" 2>/dev/null | tr -d '\r' || true)"
if [[ -z "$pid" ]]; then
  echo "::error::CampusNetManager exited during the emulator smoke period."
  exit 1
fi
append_app_log "$pid"
if grep -q 'FATAL EXCEPTION' "$log_file"; then
  echo "::error::Android emulator reported a fatal application exception."
  grep -n -A12 -B4 'FATAL EXCEPTION' "$log_file" || true
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
