FROM ghcr.io/home-assistant/aarch64-base:latest

WORKDIR /usr/src/app

COPY requirements.txt .
COPY ghp-mm2mqtt.py .
COPY serial_setup.py .
COPY mqtt_setup.py .
COPY ghp_config.py .
COPY hass-sensors.yaml .

RUN apk add --no-cache python3 py3-pip \
    && python3 -m venv /venv \
    && . /venv/bin/activate \
    && pip install --no-cache-dir -r requirements.txt \
    && deactivate

COPY run.sh ./run.sh
RUN chmod +x run.sh

CMD ["sh", "./run.sh"]