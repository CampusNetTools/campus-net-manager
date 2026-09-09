#!/bin/sh
set -eu

state_dir=/opt/homebrew/etc/campusnet-ikev2
device_file="$state_dir/devices/iphone.conf"
credentials_file="$state_dir/credentials.conf"

sed -i '' 's/^  iphone-/  eap-iphone-/' "$device_file"
{
  printf 'secrets {\n'
  sed '1,2d;$d' "$device_file"
  printf '}\n'
} > "$credentials_file"

/opt/homebrew/opt/strongswan/bin/swanctl --load-creds --clear --file "$credentials_file"
/opt/homebrew/opt/strongswan/bin/swanctl --list-certs --short
