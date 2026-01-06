#!/usr/bin/env bash
#
# Copyright 2024 Google Image Gen Skill
#
# Pre-flight environment check for Google Image Generation.
# Validates API key configuration and dependencies.
#
# Usage:
#   ./check_env.sh [skill_dir]
#
# Arguments:
#   skill_dir: Optional path to the skill directory (default: script's parent)
#
# Exit codes:
#   0: All checks passed
#   1: General error
#   2: Environment check failed (shown to Claude)

set -o errexit
set -o nounset
set -o pipefail

# Determine skill directory (where this script lives)
readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
readonly SKILL_DIR="${1:-$(dirname "${SCRIPT_DIR}")}"
readonly ENV_FILE="${SKILL_DIR}/.env"
readonly MAIN_SCRIPT="${SKILL_DIR}/main.py"

# ANSI color codes
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly NC='\033[0m'  # No Color

#######################################
# Print a success message.
# Arguments:
#   Message to print
#######################################
print_ok() {
  echo -e "${GREEN}[OK]${NC} $1"
}

#######################################
# Print an error message.
# Arguments:
#   Message to print
#######################################
print_error() {
  echo -e "${RED}[ERROR]${NC} $1"
}

#######################################
# Print a warning message.
# Arguments:
#   Message to print
#######################################
print_warn() {
  echo -e "${YELLOW}[WARN]${NC} $1"
}

#######################################
# Check if .env file exists and contains valid API key.
# Returns:
#   0 if valid, 1 if invalid
#######################################
check_env_file() {
  if [[ ! -f "${ENV_FILE}" ]]; then
    print_error ".env file not found at ${ENV_FILE}"
    echo "       Create it with: echo 'GOOGLE_AI_API_KEY=your_key' > .env"
    echo "       Get API key from: https://aistudio.google.com/apikey"
    return 1
  fi

  print_ok ".env file found"

  if ! grep -q "^GOOGLE_AI_API_KEY=" "${ENV_FILE}"; then
    print_error "GOOGLE_AI_API_KEY not found in .env"
    echo "       Add: GOOGLE_AI_API_KEY=your_key_here"
    return 1
  fi

  local key_value
  key_value="$(grep "^GOOGLE_AI_API_KEY=" "${ENV_FILE}" | cut -d'=' -f2)"

  if [[ -z "${key_value}" ]] \
      || [[ "${key_value}" == "your_key_here" ]] \
      || [[ "${key_value}" == "your_api_key_here" ]]; then
    print_error "GOOGLE_AI_API_KEY contains placeholder value"
    echo "       Edit .env and set your actual API key"
    return 1
  fi

  print_ok "GOOGLE_AI_API_KEY is configured"
  return 0
}

#######################################
# Check if uv package manager is installed.
# Returns:
#   0 if installed, 1 if not (warning only)
#######################################
check_uv_installed() {
  if command -v uv &> /dev/null; then
    print_ok "uv package manager is installed"
    return 0
  fi

  print_warn "uv package manager not found"
  echo "       Install: curl -LsSf https://astral.sh/uv/install.sh | sh"
  echo "       Alternative: use pip directly"
  return 0  # Warning only, not a blocker
}

#######################################
# Check if main.py exists.
# Returns:
#   0 if exists, 1 if not
#######################################
check_main_script() {
  if [[ -f "${MAIN_SCRIPT}" ]]; then
    print_ok "main.py found"
    return 0
  fi

  print_error "main.py not found at ${MAIN_SCRIPT}"
  return 1
}

#######################################
# Main entry point.
#######################################
main() {
  local checks_passed=true

  echo "=== Google Image Gen Environment Check ==="
  echo "Skill directory: ${SKILL_DIR}"
  echo ""

  check_env_file || checks_passed=false
  check_uv_installed
  check_main_script || checks_passed=false

  echo ""

  if [[ "${checks_passed}" == true ]]; then
    echo -e "${GREEN}=== All checks passed! Ready to generate images. ===${NC}"
    exit 0
  else
    echo -e "${RED}=== Environment check failed. Fix issues above. ===${NC}"
    exit 2
  fi
}

main "$@"