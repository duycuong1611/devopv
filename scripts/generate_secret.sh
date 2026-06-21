#!/usr/bin/env bash
set -euo pipefail
python3 -c 'import secrets; print(secrets.token_hex(32))'
