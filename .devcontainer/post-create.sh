#! /bin/bash

######################################
# KIOTA (OPENAPI CODE GENERATOR)
########################################
TMP_DIR=$(mktemp -d)

ARCH=$(uname -m)
if [ "$ARCH" = "x86_64" ]; then
  FILE="linux-x64.zip"
elif [ "$ARCH" = "aarch64" ] || [ "$ARCH" = "arm64" ]; then
  FILE="linux-arm64.zip"
else
  echo "Unsupported architecture: $ARCH"
  exit 1
fi

curl -L https://aka.ms/get/kiota/latest/linux-x64.zip -o "$TMP_DIR/kiota.zip" \
    && unzip "$TMP_DIR/kiota.zip" -d "$TMP_DIR" \
    && sudo mv "$TMP_DIR/kiota" /usr/local/bin/kiota \
    && sudo chmod +x /usr/local/bin/kiota \
    && rm -rf "$TMP_DIR"

############################
# Install dependencies
############################
uv sync --all-groups