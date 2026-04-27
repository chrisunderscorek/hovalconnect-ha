FROM ghcr.io/home-assistant/base:latest

ARG BUILD_ARCH=amd64
ARG BUILD_VERSION=dev

LABEL \
    io.hass.name="Hoval Connect" \
    io.hass.description="Installs the Hoval Connect custom integration into Home Assistant" \
    io.hass.type="app" \
    io.hass.version="${BUILD_VERSION}" \
    io.hass.arch="${BUILD_ARCH}"

WORKDIR /app

RUN apk add --no-cache coreutils

COPY custom_components/hovalconnect /app/custom_components/hovalconnect
COPY hovalconnect/run.sh /run.sh

RUN chmod a+x /run.sh

CMD ["/run.sh"]
