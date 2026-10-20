#!/bin/sh
exec "${M19_PY:-python3}" "$(dirname "$0")/m19_stub.py" vulnerable "$@"
