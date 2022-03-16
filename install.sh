#!/bin/bash

mkdir -p /opt/bgfsensormon
cp {main.py,sensor_config.txt} /opt/bgfsensormon
cp bgfsensormon.service /etc/systemd/system/bgfsensormon.service
systemctl daemon-reload
systemctl enable bgfsensormon.service
systemctl start bgfsensormon.service