#!/usr/bin/env bash

DOCKER_IMAGE="registry.supercroy.com/updrytwist/battery-hawk:latest"
COMMAND="python -m battery_hawk"

docker pull "$DOCKER_IMAGE"

if [[ $# -eq 0 ]]; then
	set -- "scan"
fi

# Execute a scan using our Docker image
# Execute battery-hawk scan with the parameters passed to this script
docker run --rm \
	--net=host \
	--privileged \
	--cap-add=NET_ADMIN \
	--cap-add=SYS_ADMIN \
	--name=battery-hawk-scan \
	--label "com.centurylinklabs.watchtower.enable=false" \
	-v /var/run/dbus:/var/run/dbus:ro \
	-v "$(pwd)"/local-instance/data:/data \
	-e "BATTERYHAWK_SYSTEM_LOGGING_LEVEL=INFO" \
	"${DOCKER_IMAGE}" \
	"${COMMAND}" \
	"$@"
