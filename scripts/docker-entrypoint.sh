#!/bin/sh
set -eu
mkdir -p /freqtrade/user_data /freqtrade/user_data/logs
python3 /freqtrade/scripts/render_config.py /freqtrade/config.json.template /freqtrade/user_data/config.json
exec freqtrade "$@"
