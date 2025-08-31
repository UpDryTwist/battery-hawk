#!/usr/bin/env bash

DOCKER_IMAGE="registry.supercroy.com/updrytwist/battery-hawk:latest"
COMMAND="python3 /app/battery_hawk scan"

docker pull $DOCKER_IMAGE

# Execute a scan using our Docker image
# Execute battery-hawk scan with the parameters passed to this script
docker run --rm \
	--net=host \
	--name=battery-hawk-scan \
	--label "com.centurylinklabs.watchtower.enable=false" \
	-e "BATTERYHAWK_SYSTEM_LOGGING_LEVEL=DEBUG" \
	${DOCKER_IMAGE} \
	"${COMMAND}" \
	"$@"
