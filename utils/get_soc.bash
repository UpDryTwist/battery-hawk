#!/usr/bin/env bash
# Fetch State of Charge (SoC) readings from Battery Hawk API
#
# Outputs lines in the form:
#   <MAC> <YYYY-MM-DD HH:MM:SS ±ZZZZ> <state_of_charge> <voltage>
#
# Usage:
#   utils/get_soc.bash [--url URL] [--device MAC] [--num N]
#
# Options (can also be set via environment variables):
#   --url, -u      API base URL without trailing /api (env: API_URL | BH_API_URL | BATTERY_HAWK_API_URL)
#                  Default: http://localhost:5000
#   --device, -d   Device MAC address to query (env: DEVICE_MAC | BH_DEVICE_MAC)
#                  If omitted, all devices are queried
#   --num, -n      Number of readings to fetch per device (env: READINGS_COUNT)
#                  Default: 1 (uses /latest endpoint)
#
# Examples:
#   utils/get_soc.bash
#   utils/get_soc.bash -u http://localhost:5000 -d AA:BB:CC:DD:EE:FF
#   utils/get_soc.bash --num 5 --device AA:BB:CC:DD:EE:FF
#   API_URL=http://myhost:5000 READINGS_COUNT=3 utils/get_soc.bash

set -euo pipefail

# --- Dependencies ------------------------------------------------------------
need_cmd() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "Error: Required command '$1' not found in PATH" >&2
		exit 127
	}
}

need_cmd curl
need_cmd jq

# --- Args & Env --------------------------------------------------------------
API_URL_DEFAULT="http://localhost:5000"
API_URL=${API_URL:-${BH_API_URL:-${BATTERY_HAWK_API_URL:-$API_URL_DEFAULT}}}
DEVICE_MAC=${DEVICE_MAC:-${BH_DEVICE_MAC:-""}}
READINGS_COUNT=${READINGS_COUNT:-1}

print_help() {
	sed -n '1,80p' "$0" | sed 's/^# \{0,1\}//'
}

# Parse CLI flags
while [[ $# -gt 0 ]]; do
	case "$1" in
	-u | --url)
		API_URL="$2"
		shift 2
		;;
	-d | --device)
		DEVICE_MAC="$2"
		shift 2
		;;
	-n | --num)
		READINGS_COUNT="$2"
		shift 2
		;;
	-h | --help)
		print_help
		exit 0
		;;
	--)
		shift
		break
		;;
	-*)
		echo "Unknown option: $1" >&2
		print_help
		exit 2
		;;
	*) # positional args not used
		echo "Unexpected argument: $1" >&2
		print_help
		exit 2
		;;
	esac
done

# Normalize
API_BASE="${API_URL%%/}"
# Accept URLs that already include /api by stripping a trailing /api segment
if [[ "$API_BASE" == */api ]]; then
	API_BASE="${API_BASE%/api}"
fi
if [[ -z "$READINGS_COUNT" ]]; then READINGS_COUNT=1; fi
if ! [[ "$READINGS_COUNT" =~ ^[0-9]+$ ]]; then
	echo "Error: --num must be an integer" >&2
	exit 2
fi

# --- Helpers -----------------------------------------------------------------
http_get() {
	local path="$1" # must start with /
	curl -sS -f -H 'Accept: application/json' "${API_BASE}${path}"
}

# Convert timestamp to local timezone in "YYYY-MM-DD HH:MM:SS ±ZZZZ". If conversion fails, return original
to_local() {
	local ts="$1"
	if [[ -z "$ts" || "$ts" == "null" ]]; then
		echo "$ts"
		return 0
	fi
	if local_dt=$(date -d "$ts" +"%Y-%m-%d %H:%M:%S %z" 2>/dev/null); then
		echo "$local_dt"
	else
		# Some systems use BSD date; try -j -f fallback (best effort)
		if local_dt=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "$ts" +"%Y-%m-%d %H:%M:%S %z" 2>/dev/null); then
			echo "$local_dt"
		else
			echo "$ts"
		fi
	fi
}

# Output one or more lines: "<mac> <timestamp> <soc> <voltage>"
print_latest_for_device() {
	local mac="$1"
	if resp=$(http_get "/api/readings/${mac}/latest" 2>/dev/null); then
		echo "$resp" | jq -r '
      .data.attributes as $a |
      select($a.state_of_charge != null) |
      "\($a.timestamp)\t\($a.state_of_charge)\t\($a.voltage)"' |
			while IFS=$'\t' read -r ts soc volt; do
				printf "%s %s %s %s\n" "$mac" "$(to_local "$ts")" "$soc" "$volt"
			done
		return 0
	fi

	# Fallback: try device details latest_reading
	if resp=$(http_get "/api/devices/${mac}" 2>/dev/null); then
		echo "$resp" | jq -r '
      .data.attributes as $a |
      select($a.latest_reading and $a.latest_reading.state_of_charge != null) |
      "\(($a.last_reading_time // ("@" + ($a.latest_reading.timestamp|tostring))))\t\($a.latest_reading.state_of_charge)\t\($a.latest_reading.voltage)"' |
			while IFS=$'\t' read -r ts soc volt; do
				printf "%s %s %s %s\n" "$mac" "$(to_local "$ts")" "$soc" "$volt"
			done
		return 0
	fi

	# If all else fails, stay quiet but return failure (device may have no readings)
	return 1
}

print_many_for_device() {
	local mac="$1"
	local limit="$2"
	if ! resp=$(http_get "/api/readings/${mac}?limit=${limit}"); then
		echo "Warning: failed to fetch readings for ${mac}" >&2
		return 1
	fi
	echo "$resp" | jq -r '
    .data[]?.attributes |
    select(.state_of_charge != null) |
    "\(.timestamp)\t\(.state_of_charge)\t\(.voltage)"' |
		while IFS=$'\t' read -r ts soc volt; do
			printf "%s %s %s %s\n" "$mac" "$(to_local "$ts")" "$soc" "$volt"
		done
}

list_all_device_macs() {
	if ! resp=$(http_get "/api/devices"); then
		echo "Error: failed to list devices from ${API_BASE}/api/devices" >&2
		exit 1
	fi
	echo "$resp" | jq -r '.data[]?.id'
}

# --- Main --------------------------------------------------------------------
if [[ -n "${DEVICE_MAC}" ]]; then
	# Specific device
	if [[ "$READINGS_COUNT" -le 1 ]]; then
		print_latest_for_device "$DEVICE_MAC"
	else
		print_many_for_device "$DEVICE_MAC" "$READINGS_COUNT"
	fi
else
	# All devices
	while IFS= read -r mac; do
		[[ -z "$mac" ]] && continue
		if [[ "$READINGS_COUNT" -le 1 ]]; then
			print_latest_for_device "$mac" || true
		else
			print_many_for_device "$mac" "$READINGS_COUNT" || true
		fi
	done < <(list_all_device_macs)
fi
