FROM python:3.13-slim AS builder

WORKDIR /app

RUN pip install poetry

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_CREATE=true \
    POETRY_VIRTUALENVS_IN_PROJECT=true \
    POETRY_CACHE_DIR='/tmp/poetry_cache'\
    PATH="/app/.venv/bin:$PATH" \
    USER=dockeruser \
    USER_ID=1000 \
    GROUP=dockergroup \
    GROUP_ID=1000

COPY --chown=${USER}:${GROUP} --chmod=0755 pyproject.toml poetry.lock README.md /app/

RUN poetry install --without dev --no-root && rm -rf $POETRY_CACHE_DIR

FROM python:3.13-slim AS runtime

WORKDIR /app

ENV VIRTUAL_ENV=/app/.venv \
    PATH="/app/.venv/bin:$PATH" \
    USER=dockeruser \
    USER_ID=1000 \
    GROUP=dockergroup \
    GROUP_ID=1000

RUN apt-get update && apt-get install -y \
    gosu procps \
    bluetooth \
    bluez \
    dbus \
    systemd \
    systemd-sysv \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid "${GROUP_ID}" "${GROUP}" && \
    useradd \
        --uid "${USER_ID}" \
        --gid "${GROUP}" \
        --create-home \
        --home /var/empty \
        --shell /bin/nologin \
        "${USER}" && \
    mkdir -p /config /data /logs && \
    chown -R "${USER}":"${GROUP}" /config /logs && \
    chmod -R a+rwX /config /logs

COPY --from=builder --chown=${USER}:${GROUP} --chmod=0755 ${VIRTUAL_ENV} ${VIRTUAL_ENV}

COPY --chown=${USER}:${GROUP} --chmod=0755 src/battery_hawk /app/battery_hawk
COPY --chown=${USER}:${GROUP} --chmod=0755 src/battery_hawk_driver /app/battery_hawk_driver
COPY --chown=${USER}:${GROUP} --chmod=0755 run_scripts /app/run_scripts
COPY --chown=${USER}:${GROUP} --chmod=0755 utils       /app/utils
# COPY --chown=${USER}:${GROUP} --chmod=a+rw default_config /config

# USER "${USER}"

# Set up the environment variables we're expecting
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/app \
    LOGFILE=/logs/battery_hawk.log \
    BATTERYHAWK_SYSTEM_LOGGING_FILE=/logs/battery_hawk.log

# TODO:
#    CONFIGFILE=/config/battery_hawk.yaml \

# Required Docker run options for BLE:
# --cap-add=NET_ADMIN --net=host --privileged
# These capabilities are needed for BLE adapter control

VOLUME /config /logs

EXPOSE 5000

ENTRYPOINT ["/app/run_scripts/start_module.sh"]
