#!/usr/bin/env bash
# Fetch State of Charge (SoC) readings from Battery Hawk via MQTT
#
# Outputs lines in the form:
#   <MAC> <YYYY-MM-DD HH:MM:SS ±ZZZZ> <state_of_charge> <voltage>
#
# Usage:
#   utils/get_soc_mqtt.bash [--host HOST] [--port PORT] [--username USER] [--password PASS] \
#                           [--device MAC] [--num N] [--prefix PREFIX] [--idle-seconds N] [--all-current]
#
# Options (can also be set via environment variables):
#   --host, -H        MQTT broker host (env: MQTT_HOST | BH_MQTT_HOST)           Default: localhost
#   --port, -p        MQTT broker port (env: MQTT_PORT | BH_MQTT_PORT)           Default: 1883
#   --username, -U    MQTT username (env: MQTT_USERNAME | BH_MQTT_USERNAME)
#   --password, -P    MQTT password (env: MQTT_PASSWORD | BH_MQTT_PASSWORD)
#   --device, -d      Device MAC address to filter (env: DEVICE_MAC | BH_DEVICE_MAC)
#                     If omitted, subscribes to all devices (wildcard)
#   --num, -n         Number of readings to fetch (env: READINGS_COUNT)          Default: 1
#                     - With --device: fetch N messages for that device then exit
#                     - Without --device: fetch N total messages across all devices then exit
#   --prefix          MQTT topic prefix (env: MQTT_PREFIX | BH_MQTT_PREFIX)       Default: battery_hawk
#   --idle-seconds    Exit after N seconds without receiving a message (env: IDLE_SECONDS | BH_IDLE_SECONDS)
#                     Uses mosquitto_sub -W N. Useful to read retained "current" statuses and quit.
#   --all-current     Convenience: wildcard devices, no --num/-C, and --idle-seconds 2 unless explicitly set
#                     (env: ALL_CURRENT | BH_ALL_CURRENT). Overrides --device if both are provided.
#
# Examples:
#   utils/get_soc_mqtt.bash
#   utils/get_soc_mqtt.bash -H mqtt.local -U user -P pass -d AA:BB:CC:DD:EE:FF
#   utils/get_soc_mqtt.bash --num 5

set -euo pipefail

# --- Dependencies ------------------------------------------------------------
need_cmd() {
	command -v "$1" >/dev/null 2>&1 || {
		echo "Error: Required command '$1' not found in PATH" >&2
		exit 127
	}
}

need_cmd mosquitto_sub
need_cmd jq

# --- Args & Env --------------------------------------------------------------
MQTT_HOST=${MQTT_HOST:-${BH_MQTT_HOST:-"localhost"}}
MQTT_PORT=${MQTT_PORT:-${BH_MQTT_PORT:-1883}} # numeric
MQTT_USERNAME=${MQTT_USERNAME:-${BH_MQTT_USERNAME:-""}}
MQTT_PASSWORD=${MQTT_PASSWORD:-${BH_MQTT_PASSWORD:-""}}
MQTT_PREFIX=${MQTT_PREFIX:-${BH_MQTT_PREFIX:-"batteryhawk"}}
DEVICE_MAC=${DEVICE_MAC:-${BH_DEVICE_MAC:-""}}
READINGS_COUNT=${READINGS_COUNT:-1}
IDLE_SECONDS=${IDLE_SECONDS:-${BH_IDLE_SECONDS:-""}}
ALL_CURRENT=${ALL_CURRENT:-${BH_ALL_CURRENT:-""}}

print_help() {
	sed -n '1,120p' "$0" | sed 's/^# \{0,1\}//'
}

# Parse CLI flags
while [[ $# -gt 0 ]]; do
	case "$1" in
	-H | --host)
		MQTT_HOST="$2"
		shift 2
		;;
	-p | --port)
		MQTT_PORT="$2"
		shift 2
		;;
	-U | --username)
		MQTT_USERNAME="$2"
		shift 2
		;;
	-P | --password)
		MQTT_PASSWORD="$2"
		shift 2
		;;
	--prefix)
		MQTT_PREFIX="$2"
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
	--idle-seconds)
		IDLE_SECONDS="$2"
		shift 2
		;;
	--all-current)
		ALL_CURRENT=1
		shift 1
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
	*)
		echo "Unexpected argument: $1" >&2
		print_help
		exit 2
		;;
	esac
done

# Normalize/validate
if ! [[ "$MQTT_PORT" =~ ^[0-9]+$ ]]; then
	echo "Error: --port must be an integer" >&2
	exit 2
fi
if [[ -z "$READINGS_COUNT" ]]; then READINGS_COUNT=1; fi
if ! [[ "$READINGS_COUNT" =~ ^[0-9]+$ ]]; then
	echo "Error: --num must be an integer" >&2
	exit 2
fi
if [[ -n "$IDLE_SECONDS" && ! "$IDLE_SECONDS" =~ ^[0-9]+$ ]]; then
	echo "Error: --idle-seconds must be an integer" >&2
	exit 2
fi

TOPIC_PREFIX="${MQTT_PREFIX%%/}"
# --all-current implies wildcard subscription, no per-device filter, and no count limit
if [[ -n "$ALL_CURRENT" ]]; then
	DEVICE_MAC=""
	READINGS_COUNT=0
fi
if [[ -n "$DEVICE_MAC" ]]; then
	SUB_TOPIC="$TOPIC_PREFIX/device/$DEVICE_MAC/status"
else
	SUB_TOPIC="$TOPIC_PREFIX/device/+/status"
	# Default behavior for wildcard: fetch a snapshot of all retained statuses
	# Unless user explicitly set --num or --idle-seconds, use idle snap mode
	if [[ "$READINGS_COUNT" -eq 1 && -z "$ALL_CURRENT" && -z "$IDLE_SECONDS" ]]; then
		READINGS_COUNT=0
		IDLE_SECONDS=2
	fi
fi

# --- Helpers -----------------------------------------------------------------
# Convert timestamp to local timezone in "YYYY-MM-DD HH:MM:SS ±ZZZZ"
to_local() {
	local ts="$1"
	if [[ -z "$ts" || "$ts" == "null" ]]; then
		echo "$ts"
		return 0
	fi
	if local_dt=$(date -d "$ts" +"%Y-%m-%d %H:%M:%S %z" 2>/dev/null); then
		echo "$local_dt"
	else
		# Best-effort BSD/macOS fallback
		if local_dt=$(date -j -f "%Y-%m-%dT%H:%M:%S%z" "$ts" +"%Y-%m-%d %H:%M:%S %z" 2>/dev/null); then
			echo "$local_dt"
		else
			echo "$ts"
		fi
	fi
}

build_mosq_cmd() {
	local -n _out=$1
	_out=(mosquitto_sub -h "$MQTT_HOST" -p "$MQTT_PORT" -t "$SUB_TOPIC" -q 1)
	if [[ -n "$MQTT_USERNAME" ]]; then _out+=(-u "$MQTT_USERNAME"); fi
	if [[ -n "$MQTT_PASSWORD" ]]; then _out+=(-P "$MQTT_PASSWORD"); fi
	# If --all-current was provided and IDLE_SECONDS is empty, default to 2s idle exit
	local _idle="$IDLE_SECONDS"
	if [[ -n "$ALL_CURRENT" && -z "$_idle" ]]; then _idle=2; fi
	# Count messages (if specified) and/or exit on idle
	if [[ "$READINGS_COUNT" -gt 0 ]]; then _out+=(-C "$READINGS_COUNT"); fi
	if [[ -n "$_idle" ]]; then _out+=(-W "$_idle"); fi
}

# --- Main --------------------------------------------------------------------
# Subscribe and pipe JSON payloads to jq, then print formatted lines
mosq_cmd=()
build_mosq_cmd mosq_cmd

# echo "Polling for $READINGS_COUNT messages on topic $SUB_TOPIC..."
# echo "${mosq_cmd[*]}"

"${mosq_cmd[@]}" 2> >(grep -v -E '^(Timed out|Error: Timed out)$' >&2) |
	jq -cr '
	  # Prefer top-level fields; fall back to nested latest_reading
	  def pick(f): if .[f] != null then .[f] else (.latest_reading?[f]) end;
	  select(.device_id != null and .timestamp != null)
	  | [ .device_id, .timestamp, pick("state_of_charge"), pick("voltage") ]
	  | @tsv
	' |
	while IFS=$'\t' read -r mac ts soc volt; do
		# Fallback to parsing MAC from topic is not needed since payload includes device_id
		printf "%s %s %s %s\n" "$mac" "$(to_local "$ts")" "$soc" "${volt:-}"
	done
