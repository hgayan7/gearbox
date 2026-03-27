#!/bin/bash
set -e

SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    TARGET="$(readlink "$SOURCE")"
    if [[ "$TARGET" != /* ]]; then
        SOURCE="$DIR/$TARGET"
    else
        SOURCE="$TARGET"
    fi
done

SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
APP_CONTENTS="$(cd "$SCRIPT_DIR/.." && pwd)"

export PATH="$PATH"
exec "$APP_CONTENTS/Resources/venv/bin/python3" "$APP_CONTENTS/Resources/python/cli.py" "$@"
