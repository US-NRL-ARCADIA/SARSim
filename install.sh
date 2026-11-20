#!/usr/bin/env bash

# SARSim bootstrap installer for macOS and Windows Subsystem for Linux (WSL).
# This script intentionally uses syntax supported by macOS's Bash 3.2.

set -Eeuo pipefail
IFS=$'\n\t'

REPOSITORY_URL="${SARSIM_REPO_URL:-https://github.com/US-NRL-ARCADIA/SARSim.git}"
REPOSITORY_REF="${SARSIM_REF:-}"
INSTALL_DIR="${SARSIM_INSTALL_DIR:-}"
TEMP_DIR=""
VENV_TEMP=""
PLATFORM=""
CURRENT_STEP=""

say() {
  printf '\n==> %s\n' "$*"
}

note() {
  printf '    %s\n' "$*"
}

warn() {
  printf '\nWARNING: %s\n' "$*" >&2
}

die() {
  printf '\nERROR: %s\n' "$*" >&2
  exit 1
}

cleanup() {
  if [ -n "$VENV_TEMP" ] && [ -d "$VENV_TEMP" ]; then
    rm -rf -- "$VENV_TEMP" || true
  fi
  if [ -n "$TEMP_DIR" ] && [ -d "$TEMP_DIR" ]; then
    rm -rf -- "$TEMP_DIR" || true
  fi
}

show_repair_advice() {
  case "$CURRENT_STEP" in
    *Homebrew*)
      cat >&2 <<'EOF'

Homebrew could not complete the requested operation. Diagnose it with:
  brew update
  brew doctor

If brew is installed but not found in a new terminal, run the command matching
your Mac, then retry this installer:
  eval "$(/opt/homebrew/bin/brew shellenv)"   # Apple Silicon
  eval "$(/usr/local/bin/brew shellenv)"      # Intel
EOF
      ;;
    *APT*|*apt*|*NodeSource*)
      cat >&2 <<'EOF'

APT may have been interrupted, locked by another updater, or left with broken
packages. Wait for other updates to finish, then run:
  sudo dpkg --configure -a
  sudo apt-get -f install
  sudo apt-get update

Do not delete files under /var/lib/dpkg or APT lock files by hand.
EOF
      ;;
    *clone*)
      cat >&2 <<EOF

Check DNS, HTTPS access, and any required proxy or VPN, then retry:
  git ls-remote "$REPOSITORY_URL" HEAD

If your network requires a proxy, configure HTTPS_PROXY for both curl and Git.
EOF
      ;;
    *virtual*|*packaging*|*Python*)
      cat >&2 <<EOF

The Python environment may be incomplete. Preserve it and retry with:
  mv "$INSTALL_DIR/.venv" "$INSTALL_DIR/.venv.failed"
  bash "$INSTALL_DIR/install.sh"

If .venv does not exist, just rerun the installer. Check free space with:
  df -h "$INSTALL_DIR"
EOF
      ;;
    *UI*|*npm*)
      cat >&2 <<EOF

Check the first npm error above. Common recovery commands are:
  node --version                     # must be v20 or newer
  npm cache verify
  cd "$INSTALL_DIR" && npm --prefix ui ci

Do not use "sudo npm" and do not run "npm audit fix --force". If npm reports
EACCES for ~/.npm, repair ownership, then retry:
  sudo chown -R "$(id -u):$(id -g)" "$HOME/.npm"
EOF
      ;;
    *)
      cat >&2 <<'EOF'

Check the error above, available disk space, and HTTPS connectivity. After
repairing the reported problem, rerun the installer; completed steps are safe
to repeat.
EOF
      ;;
  esac
}

on_error() {
  status="$1"
  line="$2"
  failed_command="$3"
  trap - ERR
  printf '\nERROR: Installation failed during: %s\n' "${CURRENT_STEP:-an unexpected command}" >&2
  printf '       Line %s exited with status %s.\n' "$line" "$status" >&2
  printf '       Command: %s\n' "$failed_command" >&2
  show_repair_advice
  exit "$status"
}

trap 'on_error "$?" "$LINENO" "$BASH_COMMAND"' ERR
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

run_step() {
  description="$1"
  shift
  CURRENT_STEP="$description"
  say "$description"
  "$@"
  CURRENT_STEP=""
}

usage() {
  cat <<'EOF'
Install SARSim and its Python and browser-UI dependencies.

Usage:
  bash install.sh [--install-dir PATH] [--repo URL] [--ref BRANCH_OR_TAG]

Options:
  --install-dir PATH  Destination checkout (default: current directory when
                      empty, otherwise ./SARSim)
  --repo URL          Git repository to clone
  --ref REF           Branch or tag to clone
  -h, --help          Show this help

The same settings can be supplied through SARSIM_INSTALL_DIR,
SARSIM_REPO_URL, and SARSIM_REF. An existing SARSim checkout is reused but is
never pulled, reset, or switched to another branch automatically.
EOF
}

parse_arguments() {
  while [ "$#" -gt 0 ]; do
    case "$1" in
      --install-dir)
        [ "$#" -ge 2 ] || die "--install-dir requires a path."
        INSTALL_DIR="$2"
        shift 2
        ;;
      --repo)
        [ "$#" -ge 2 ] || die "--repo requires a URL."
        REPOSITORY_URL="$2"
        shift 2
        ;;
      --ref)
        [ "$#" -ge 2 ] || die "--ref requires a branch or tag."
        REPOSITORY_REF="$2"
        shift 2
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Unknown option: $1 (run with --help for usage)."
        ;;
    esac
  done
}

is_sarsim_checkout() {
  directory="$1"
  [ -f "$directory/pyproject.toml" ] &&
    [ -f "$directory/ui/package-lock.json" ] &&
    grep -Eq '^[[:space:]]*name[[:space:]]*=[[:space:]]*"sarsim"' \
      "$directory/pyproject.toml"
}

choose_install_directory() {
  [ -z "$INSTALL_DIR" ] || return 0

  if is_sarsim_checkout "$PWD" || [ -z "$(ls -A "$PWD" 2>/dev/null)" ]; then
    INSTALL_DIR="$PWD"
  else
    INSTALL_DIR="$PWD/SARSim"
    note "The current directory is not empty; SARSim will be installed in $INSTALL_DIR."
  fi
}

detect_platform() {
  case "$(uname -s)" in
    Darwin)
      PLATFORM="macos"
      case "$(uname -m)" in
        arm64|x86_64) ;;
        *) die "Unsupported Mac architecture: $(uname -m)." ;;
      esac
      ;;
    Linux)
      if [ -n "${WSL_INTEROP:-}" ] ||
        grep -Eqi '(microsoft|wsl)' /proc/sys/kernel/osrelease 2>/dev/null; then
        PLATFORM="wsl"
      else
        die "This installer supports macOS and WSL. Native Linux users should follow README.md."
      fi
      ;;
    *)
      die "Unsupported operating system: $(uname -s). Use macOS or run from a WSL shell."
      ;;
  esac

  if [ "$(id -u)" -eq 0 ]; then
    if [ "$PLATFORM" = "wsl" ]; then
      cat >&2 <<'EOF'

ERROR: Do not install SARSim as root. If WSL has no normal user yet, create one:
  adduser YOUR_USERNAME
  usermod -aG sudo YOUR_USERNAME
  su - YOUR_USERNAME

Then download and run this installer again as that user. It uses sudo only for
system packages.
EOF
      exit 1
    fi
    die "Do not use sudo. Return to your normal macOS account and run the installer again."
  fi
}

check_basics() {
  [ -n "${HOME:-}" ] || die "HOME is not set. Start a normal login shell and retry."
  [ -d "$HOME" ] && [ -w "$HOME" ] || die "HOME is not a writable directory: $HOME"
  command -v curl >/dev/null 2>&1 || die "curl is required to run the installer."

  case "$INSTALL_DIR" in
    /mnt/*)
      warn "Installing under /mnt can make npm much slower and can cause permission problems."
      note "Prefer a WSL path such as $HOME/SARSim."
      ;;
  esac
}

download() {
  url="$1"
  destination="$2"
  curl --fail --location --silent --show-error \
    --retry 3 --connect-timeout 15 --max-time 300 \
    --output "$destination" "$url"
}

configure_brew_path() {
  brew_command="$1"
  shell_name="$(basename -- "${SHELL:-zsh}")"
  case "$shell_name" in
    zsh) profile="$HOME/.zprofile" ;;
    bash) profile="$HOME/.bash_profile" ;;
    *) profile="$HOME/.profile" ;;
  esac

  shellenv_line="eval \"\$($brew_command shellenv)\""
  if [ ! -e "$profile" ] ||
    ! grep -F "$brew_command shellenv" "$profile" >/dev/null 2>&1; then
    if [ -e "$profile" ] && [ ! -w "$profile" ]; then
      warn "Could not update $profile. Add this line yourself:"
      note "$shellenv_line"
    else
      printf '\n%s\n' "$shellenv_line" >> "$profile"
      note "Added Homebrew to PATH in $profile."
    fi
  fi
}

install_macos_prerequisites() {
  if ! xcode-select -p >/dev/null 2>&1; then
    say "Requesting Apple's Command Line Tools"
    xcode-select --install >/dev/null 2>&1 || true
    cat >&2 <<'EOF'

Apple's Command Line Tools are required. Complete the installer window, then
rerun this script. If no window appeared, run:
  xcode-select --install

If macOS says the tools are installed but xcode-select still fails, run:
  sudo xcode-select --reset
EOF
    exit 1
  fi

  brew_needs_path_configuration=0
  brew_command="$(command -v brew || true)"
  if [ -z "$brew_command" ]; then
    for candidate in /opt/homebrew/bin/brew /usr/local/bin/brew; do
      if [ -x "$candidate" ]; then
        brew_command="$candidate"
        brew_needs_path_configuration=1
        break
      fi
    done
  fi

  if [ -z "$brew_command" ]; then
    command -v sudo >/dev/null 2>&1 ||
      die "sudo is required to install Homebrew. Ask an administrator to install Homebrew first."
    if ! sudo -v; then
      die "Administrator authentication failed. Ask an administrator to install Homebrew first."
    fi
    run_step "Downloading the official Homebrew installer" \
      download "https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh" \
      "$TEMP_DIR/homebrew-install.sh"
    CURRENT_STEP="Installing Homebrew"
    say "$CURRENT_STEP"
    NONINTERACTIVE=1 /bin/bash "$TEMP_DIR/homebrew-install.sh"
    CURRENT_STEP=""

    case "$(uname -m)" in
      arm64) brew_command="/opt/homebrew/bin/brew" ;;
      *) brew_command="/usr/local/bin/brew" ;;
    esac
    [ -x "$brew_command" ] || die "Homebrew finished but $brew_command was not created."
    brew_needs_path_configuration=1
  fi

  CURRENT_STEP="Loading the Homebrew environment"
  eval "$("$brew_command" shellenv)"
  CURRENT_STEP=""
  if [ "$brew_needs_path_configuration" -eq 1 ]; then
    configure_brew_path "$brew_command"
  fi

  if ! python_supported python3.12; then
    run_step "Installing Python 3.12 with Homebrew" \
      "$brew_command" install python@3.12
  fi
  if ! node_supported || ! command -v npm >/dev/null 2>&1; then
    run_step "Installing Node.js with Homebrew" "$brew_command" install node
  fi

  if ! command -v pkg-config >/dev/null 2>&1 ||
    ! pkg-config --exists sdl2 SDL2_image SDL2_mixer SDL2_ttf freetype2 2>/dev/null; then
    run_step "Installing Pygame native build dependencies with Homebrew" \
      "$brew_command" install pkg-config sdl2 sdl2_image sdl2_mixer sdl2_ttf portmidi
  fi

  if "$brew_command" list --versions python@3.12 >/dev/null 2>&1; then
    PATH="$("$brew_command" --prefix python@3.12)/bin:$PATH"
  fi
  if "$brew_command" list --versions node >/dev/null 2>&1; then
    PATH="$("$brew_command" --prefix node)/bin:$PATH"
  fi
  export PATH
}

apt_has_candidate() {
  package="$1"
  candidate="$(apt-cache policy "$package" 2>/dev/null | awk '/Candidate:/ { print $2; exit }')"
  [ -n "$candidate" ] && [ "$candidate" != "(none)" ]
}

python_supported() {
  candidate="$1"
  command -v "$candidate" >/dev/null 2>&1 &&
    "$candidate" -c \
      'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)'
}

find_python() {
  for candidate in python3.12 python3.13 python3.11 python3; do
    if python_supported "$candidate"; then
      command -v "$candidate"
      return 0
    fi
  done
  return 1
}

node_supported() {
  command -v node >/dev/null 2>&1 || return 1
  node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || true)"
  case "$node_major" in
    ''|*[!0-9]*) return 1 ;;
  esac
  [ "$node_major" -ge 20 ]
}

install_wsl_python() {
  if PYTHON_COMMAND="$(find_python)"; then
    if ! "$PYTHON_COMMAND" -m venv --help >/dev/null 2>&1; then
      python_version="$("$PYTHON_COMMAND" -c \
        'import sys; print(f"python{sys.version_info.major}.{sys.version_info.minor}-venv")')"
      if apt_has_candidate "$python_version"; then
        run_step "Installing Python's virtual-environment module with APT" \
          sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y "$python_version"
      elif apt_has_candidate python3-venv; then
        run_step "Installing Python's virtual-environment module with APT" \
          sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y python3-venv
      fi
    fi
    return 0
  fi

  python_package=""
  for candidate in python3.12 python3.11; do
    if apt_has_candidate "$candidate"; then
      python_package="$candidate"
      break
    fi
  done

  if [ -z "$python_package" ] && [ "${ID:-}" = "ubuntu" ]; then
    warn "This Ubuntu release does not provide Python 3.11-3.13; enabling the deadsnakes PPA."
    note "To avoid third-party repositories, cancel now and upgrade the WSL distribution instead."
    run_step "Installing the Ubuntu repository helper with APT" \
      sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y software-properties-common
    run_step "Adding the deadsnakes Python PPA" \
      sudo add-apt-repository -y ppa:deadsnakes/ppa
    run_step "Refreshing APT after adding the Python PPA" sudo apt-get update
    if apt_has_candidate python3.12; then
      python_package="python3.12"
    fi
  fi

  if [ -z "$python_package" ]; then
    cat >&2 <<'EOF'

No Python 3.11 through 3.13 package is available for this WSL distribution.
Upgrade the distribution, or install Python 3.12 and its venv module manually.
For a new Ubuntu 24.04 distribution, run this in Windows PowerShell:
  wsl --install -d Ubuntu-24.04
EOF
    exit 1
  fi

  run_step "Installing $python_package and its virtual-environment module with APT" \
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    "$python_package" "$python_package-venv"
  PYTHON_COMMAND="$(command -v "$python_package")"
}

install_wsl_node() {
  if node_supported && command -v npm >/dev/null 2>&1; then
    return 0
  fi

  run_step "Downloading the official NodeSource repository setup" \
    download "https://deb.nodesource.com/setup_22.x" "$TEMP_DIR/nodesource-setup.sh"
  run_step "Configuring the Node.js 22 repository" \
    sudo -E bash "$TEMP_DIR/nodesource-setup.sh"
  run_step "Installing Node.js and npm with APT" \
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y nodejs
}

install_wsl_prerequisites() {
  command -v apt-get >/dev/null 2>&1 ||
    die "This WSL distribution does not use APT. Follow its package-manager instructions in README.md."
  command -v sudo >/dev/null 2>&1 || {
    cat >&2 <<'EOF'

ERROR: sudo is not installed. As root, install it and grant your user access:
  apt-get update && apt-get install -y sudo
  usermod -aG sudo YOUR_USERNAME
Then close WSL, reopen it as that user, and rerun this installer.
EOF
    exit 1
  }
  if ! sudo -v; then
    die "sudo authentication failed. Confirm your password and sudo group membership."
  fi

  if [ -f /etc/os-release ]; then
    # /etc/os-release is the standard source of distro metadata.
    . /etc/os-release
  fi

  run_step "Refreshing APT package metadata" sudo apt-get update
  run_step "Installing Git, curl, and trusted certificates with APT" \
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates
  run_step "Installing Pygame native build dependencies with APT" \
    sudo env DEBIAN_FRONTEND=noninteractive apt-get install -y \
    build-essential pkg-config libfreetype6-dev libjpeg-dev libportmidi-dev \
    libsdl2-dev libsdl2-image-dev libsdl2-mixer-dev libsdl2-ttf-dev
  install_wsl_python
  install_wsl_node
}

select_python() {
  if [ "$PLATFORM" = "macos" ]; then
    PYTHON_COMMAND="$(command -v python3.12 || true)"
  elif [ -z "${PYTHON_COMMAND:-}" ]; then
    PYTHON_COMMAND="$(find_python || true)"
  fi

  [ -n "$PYTHON_COMMAND" ] || die "Python 3.11 through 3.13 was installed but is not on PATH."
  python_supported "$PYTHON_COMMAND" ||
    die "$PYTHON_COMMAND is unsupported; SARSim requires Python 3.11 through 3.13."
  "$PYTHON_COMMAND" -m venv --help >/dev/null 2>&1 || {
    if [ "$PLATFORM" = "wsl" ]; then
      die "Python's venv module is missing. Install it with: sudo apt-get install python3-venv"
    fi
    die "Python's venv module is missing. Repair Python with: brew reinstall python@3.12"
  }
}

verify_node() {
  if ! node_supported; then
    node_path="$(command -v node || true)"
    cat >&2 <<EOF

ERROR: Node.js 20 or newer is required, but the active command is:
  ${node_path:-not found}

If that path contains .nvm, run "nvm install 22 && nvm use 22" and retry.
Otherwise open a new terminal so the package-manager PATH takes effect.
EOF
    exit 1
  fi
  command -v npm >/dev/null 2>&1 || die "Node.js is installed but npm is missing. Reinstall Node.js 22."
}

prepare_checkout() {
  parent_dir="$(dirname -- "$INSTALL_DIR")"
  mkdir -p -- "$parent_dir"

  available_kb="$(df -Pk "$parent_dir" | awk 'NR == 2 { print $4 }')"
  case "$available_kb" in
    ''|*[!0-9]*) ;;
    *)
      if [ "$available_kb" -lt 2097152 ]; then
        warn "Less than 2 GiB is available on the installation filesystem."
        note "Installation may fail. Check with: df -h \"$parent_dir\""
      fi
      ;;
  esac

  if [ -e "$INSTALL_DIR" ]; then
    if is_sarsim_checkout "$INSTALL_DIR"; then
      say "Using the existing SARSim checkout"
      note "$INSTALL_DIR"
      if [ -n "$REPOSITORY_REF" ]; then
        warn "--ref is ignored for an existing checkout; no branch was changed."
      fi
      return 0
    fi
    if [ -d "$INSTALL_DIR" ] && [ -z "$(ls -A "$INSTALL_DIR")" ]; then
      :
    else
      die "$INSTALL_DIR exists but is not a SARSim checkout. Move it aside or choose --install-dir."
    fi
  fi

  CURRENT_STEP="Cloning SARSim"
  say "$CURRENT_STEP"
  if [ -n "$REPOSITORY_REF" ]; then
    git clone --branch "$REPOSITORY_REF" --single-branch \
      "$REPOSITORY_URL" "$INSTALL_DIR"
  else
    git clone "$REPOSITORY_URL" "$INSTALL_DIR"
  fi
  CURRENT_STEP=""
  is_sarsim_checkout "$INSTALL_DIR" || die "The cloned repository does not have the expected SARSim files."
}

check_npm_ownership() {
  for directory in "$HOME/.npm" "$INSTALL_DIR/ui/node_modules"; do
    if [ -d "$directory" ] &&
      [ -n "$(find "$directory" ! -user "$(id -un)" -print -quit 2>/dev/null)" ]; then
      cat >&2 <<EOF

ERROR: $directory contains files owned by another user, usually from running
npm with sudo. Repair ownership and rerun the installer:
  sudo chown -R "$(id -u):$(id -g)" "$directory"
EOF
      exit 1
    fi
  done
}

install_project() {
  venv="$INSTALL_DIR/.venv"
  if [ -e "$venv" ]; then
    if [ ! -x "$venv/bin/python" ]; then
      cat >&2 <<EOF

ERROR: $venv exists but is not a complete virtual environment. Preserve it
and retry with:
  mv "$venv" "$venv.failed"
  bash "$INSTALL_DIR/install.sh"
EOF
      exit 1
    fi
    if ! "$venv/bin/python" -c \
      'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 14) else 1)'; then
      old_venv="$venv.unsupported-python"
      suffix=1
      while [ -e "$old_venv" ]; do
        old_venv="$venv.unsupported-python.$suffix"
        suffix=$((suffix + 1))
      done
      warn "$venv uses an unsupported Python version."
      note "Preserving it at $old_venv and creating a Python 3.11-3.13 environment."
      mv -- "$venv" "$old_venv"
    fi
  fi

  if [ -e "$venv" ]; then
    say "Reusing the existing Python virtual environment"
  else
    VENV_TEMP="$(mktemp -d "$INSTALL_DIR/.venv.install.XXXXXX")"
    run_step "Creating the Python virtual environment" "$PYTHON_COMMAND" -m venv "$VENV_TEMP"
    mv -- "$VENV_TEMP" "$venv"
    VENV_TEMP=""
  fi

  run_step "Updating Python packaging tools" \
    "$venv/bin/python" -m pip install --upgrade pip setuptools wheel
  CURRENT_STEP="Installing SARSim Python packages"
  say "$CURRENT_STEP"
  "$venv/bin/python" -m pip install -e "$INSTALL_DIR[dev]"
  CURRENT_STEP=""

  check_npm_ownership
  run_step "Installing the browser UI packages with npm" npm --prefix "$INSTALL_DIR/ui" ci

  run_step "Verifying Python imports" \
    "$venv/bin/python" -c 'import fastapi, numpy, pygame, src.core.engine'
  [ -x "$INSTALL_DIR/ui/node_modules/.bin/react-scripts" ] ||
    die "npm completed but react-scripts is missing from ui/node_modules."
}

print_success() {
  say "SARSim installation completed successfully"
  printf 'Installed in: %s\n' "$INSTALL_DIR"
  printf 'Python:      %s\n' "$("$INSTALL_DIR/.venv/bin/python" --version 2>&1)"
  printf 'Node.js:     %s\n' "$(node --version)"
  cat <<EOF

Start SARSim with:
  cd "$INSTALL_DIR"
  ./run.sh

Then open http://localhost:3000 in a browser.

Optional full verification:
  "$INSTALL_DIR/.venv/bin/python" -m pytest
  npm --prefix "$INSTALL_DIR/ui" run build
EOF
}

main() {
  parse_arguments "$@"
  choose_install_directory
  detect_platform
  check_basics
  TEMP_DIR="$(mktemp -d "${TMPDIR:-/tmp}/sarsim-install.XXXXXX")"

  say "Detected $PLATFORM"
  note "Installation directory: $INSTALL_DIR"

  if [ "$PLATFORM" = "macos" ]; then
    install_macos_prerequisites
  else
    install_wsl_prerequisites
  fi

  select_python
  verify_node
  command -v git >/dev/null 2>&1 || die "Git is not available after prerequisite installation."
  note "Using $("$PYTHON_COMMAND" --version 2>&1), $(node --version), and $(git --version)."

  prepare_checkout
  install_project
  print_success
}

main "$@"
