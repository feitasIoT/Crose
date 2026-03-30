#!/bin/bash

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Please run as root"
  exit 1
fi

echo "Installing CRose Agent..."

# Define paths
BIN_DIR="/usr/local/bin"
BIN_NAME="crose_agent"
BIN_PATH="$BIN_DIR/$BIN_NAME"
CONFIG_DIR="/etc/crose_agent"
CONFIG_PATH="$CONFIG_DIR/config.yaml"
SERVICE_NAME="croseagent.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"

# 1. Install binary
if [ -f "$BIN_NAME" ]; then
    echo "Installing binary to $BIN_PATH..."
    cp "$BIN_NAME" "$BIN_PATH"
    chmod +x "$BIN_PATH"
else
    echo "Error: $BIN_NAME binary not found in current directory."
    exit 1
fi

# 2. Install config
if [ -f "config.yaml" ]; then
    echo "Installing config to $CONFIG_PATH..."
    mkdir -p "$CONFIG_DIR"
    cp "config.yaml" "$CONFIG_PATH"
else
    echo "Warning: config.yaml not found. Skipping config installation."
fi

# 3. Install service
if [ -f "$SERVICE_NAME" ]; then
    echo "Installing service to $SERVICE_PATH..."
    cp "$SERVICE_NAME" "$SERVICE_PATH"
    
    # Reload systemd
    echo "Reloading systemd..."
    systemctl daemon-reload
    
    # Enable and start service
    echo "Enabling and starting service..."
    systemctl enable croseagent
    systemctl restart croseagent
    
    echo "Service installed and started."
else
    echo "Error: $SERVICE_NAME file not found."
    exit 1
fi

echo "Installation complete."
