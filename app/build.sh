#!/usr/bin/env bash
# Скрипт сборки для Render.com
set -o errexit

pip install -r requirements.txt
python init_db.py
