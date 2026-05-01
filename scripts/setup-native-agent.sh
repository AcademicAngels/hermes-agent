#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="${ENV_FILE:-$REPO_DIR/.env.agent}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  . "$ENV_FILE"
  set +a
fi

: "${HERMES_DATA_DIR:=/home/hermes_data}"
: "${HERMES_RUNTIME_DIR:=/home/hermes_runtime}"
: "${HERMES_VENV_DIR:=$HERMES_RUNTIME_DIR/venv}"
: "${UV_CACHE_DIR:=$HERMES_RUNTIME_DIR/uv-cache}"
: "${PIP_CACHE_DIR:=$HERMES_RUNTIME_DIR/pip-cache}"
: "${HOST_HINDSIGHT_API_URL:=http://localhost:18888}"
: "${HINDSIGHT_BANK_ID:=hermes}"
: "${HINDSIGHT_BUDGET:=mid}"
: "${OPENAI_IMAGE_MODEL:=gpt-image-2-medium}"
: "${WRAPPER_PATH:=/usr/local/bin/hermes}"
: "${PYTHON_BIN:=python3}"

export HERMES_HOME="$HERMES_DATA_DIR"
export UV_CACHE_DIR
export PIP_CACHE_DIR

install -d -m 755 "$HERMES_RUNTIME_DIR"
install -d -m 700 "$HERMES_DATA_DIR"
install -d -m 755 "$(dirname -- "$WRAPPER_PATH")"

if command -v uv >/dev/null 2>&1; then
  if [[ ! -x "$HERMES_VENV_DIR/bin/python" ]]; then
    uv venv "$HERMES_VENV_DIR" --python "$PYTHON_BIN"
  fi
  uv pip install --python "$HERMES_VENV_DIR/bin/python" -e "$REPO_DIR[all]"
else
  if [[ ! -x "$HERMES_VENV_DIR/bin/python" ]]; then
    "$PYTHON_BIN" -m venv "$HERMES_VENV_DIR"
  fi
  "$HERMES_VENV_DIR/bin/python" -m pip install -e "$REPO_DIR[all]"
fi

"$HERMES_VENV_DIR/bin/python" "$REPO_DIR/scripts/native_agent_config_init.py" \
  --hermes-home "$HERMES_HOME" \
  --hindsight-api-url "$HOST_HINDSIGHT_API_URL" \
  --hindsight-bank-id "$HINDSIGHT_BANK_ID" \
  --hindsight-budget "$HINDSIGHT_BUDGET" \
  --image-model "$OPENAI_IMAGE_MODEL"

wrapper_tmp="$(mktemp "${WRAPPER_PATH}.tmp.XXXXXX")"
cleanup() {
  rm -f -- "$wrapper_tmp"
}
trap cleanup EXIT

printf -v wrapper_env_file '%q' "$ENV_FILE"
printf -v wrapper_default_hermes_home '%q' "$HERMES_DATA_DIR"
printf -v wrapper_default_venv_dir '%q' "$HERMES_VENV_DIR"

cat >"$wrapper_tmp" <<EOF
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE=$wrapper_env_file
DEFAULT_HERMES_HOME=$wrapper_default_hermes_home
DEFAULT_HERMES_VENV_DIR=$wrapper_default_venv_dir
ORIGINAL_HERMES_HOME="\${HERMES_HOME:-}"

if [[ -f "\$ENV_FILE" ]]; then
  set -a
  . "\$ENV_FILE"
  set +a
fi

: "\${HERMES_DATA_DIR:=\$DEFAULT_HERMES_HOME}"
: "\${HERMES_VENV_DIR:=\$DEFAULT_HERMES_VENV_DIR}"

if [[ -n "\$ORIGINAL_HERMES_HOME" ]]; then
  export HERMES_HOME="\$ORIGINAL_HERMES_HOME"
else
  export HERMES_HOME="\${HERMES_HOME:-\$HERMES_DATA_DIR}"
fi

exec "\$HERMES_VENV_DIR/bin/hermes" "\$@"
EOF

install -m 755 "$wrapper_tmp" "$WRAPPER_PATH"
trap - EXIT
cleanup

printf 'Hermes native setup complete.\n'
printf 'Repo: %s\n' "$REPO_DIR"
printf 'Venv: %s\n' "$HERMES_VENV_DIR"
printf 'Data: %s\n' "$HERMES_DATA_DIR"
printf 'Wrapper: %s\n' "$WRAPPER_PATH"
