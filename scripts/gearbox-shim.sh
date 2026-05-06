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

BUNDLED_PYTHON="$APP_CONTENTS/Resources/venv/bin/python3"
BUNDLED_SITE_PACKAGES="$APP_CONTENTS/Resources/venv/lib/python3.11/site-packages"

if [ -d "$BUNDLED_SITE_PACKAGES" ]; then
    export PYTHONPATH="$BUNDLED_SITE_PACKAGES${PYTHONPATH:+:$PYTHONPATH}"
fi

python_candidates=(
    "$BUNDLED_PYTHON"
    "${GEARBOX_PYTHON:-}"
    "/opt/homebrew/opt/python@3.11/bin/python3.11"
    "/usr/local/opt/python@3.11/bin/python3.11"
    "/opt/homebrew/bin/python3.11"
    "/usr/local/bin/python3.11"
    "python3.11"
    "python3"
)

for python in "${python_candidates[@]}"; do
    [ -n "$python" ] || continue

    if [[ "$python" == */* ]]; then
        [ -x "$python" ] || continue
        exec "$python" "$APP_CONTENTS/Resources/python/cli.py" "$@"
    elif command -v "$python" >/dev/null 2>&1; then
        exec "$python" "$APP_CONTENTS/Resources/python/cli.py" "$@"
    fi
done

echo "Gearbox could not find a usable Python 3 interpreter." >&2
exit 127
