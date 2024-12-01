#!/bin/bash

echo "Setting up service..."
sudo cp krakensdragent.service /etc/systemd/system
sudo systemctl daemon-reload
sudo systemctl enable krakensdragent
sudo systemctl start krakensdragent
