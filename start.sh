#!/usr/bin/env zsh
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: start.sh [--no-venv] [--venv-dir DIR] [--skip-install] [--help] -- [generate.py args]

Options:
  --no-venv        Don't create/activate virtualenv, use system Python
  --venv-dir DIR   Virtualenv directory (default: .venv)
  --skip-install   Skip pip install -r requirements.txt
  --help           Show this help and exit

All arguments after `--` are forwarded to `generate.py`.
USAGE
}

# defaults
venv_dir=".venv"
use_venv=true
skip_install=false

forward_args=()

while [[ $# -gt 0 ]]; do
  case $1 in
    --no-venv)
      use_venv=false
      shift
      ;;
    --venv-dir)
      venv_dir=$2
      shift 2
      ;;
    --skip-install)
      skip_install=true
      shift
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    --)
      shift
      forward_args=("$@")
      break
      ;;
    *)
      # unknown - forward to generate.py
      forward_args+=("$1")
      shift
      ;;
  esac
done

echo "start.sh: venv_dir=${venv_dir}, use_venv=${use_venv}, skip_install=${skip_install}"

PYTHON=python3
PIP=pip3

if [[ "$use_venv" == true ]]; then
  if [[ ! -d "$venv_dir" ]]; then
    echo "Creating virtualenv in $venv_dir..."
    python3 -m venv "$venv_dir"
  fi
  source "$venv_dir/bin/activate"
  PYTHON="$venv_dir/bin/python"
  PIP="$venv_dir/bin/pip"
fi

if [[ "$skip_install" != true ]]; then
  if [[ -f "requirements.txt" ]]; then
    echo "Installing requirements from requirements.txt..."
    "$PIP" install --upgrade pip setuptools wheel >/dev/null
    "$PIP" install -r requirements.txt
  else
    echo "No requirements.txt found, skipping install."
  fi
else
  echo "Skipping dependency installation as requested."
fi

if [[ -f "getImage.sh" ]]; then
  echo "Running getImage.sh to fetch/generate images..."
  bash getImage.sh
else
  echo "Warning: getImage.sh not found, skipping."
fi

echo "Running generate.py..."
if [[ -f "generate.py" ]]; then
  "$PYTHON" generate.py "${forward_args[@]}"
else
  echo "generate.py not found in the current directory." >&2
  exit 2
fi

echo "Done."
