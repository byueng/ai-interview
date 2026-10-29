#!/usr/bin/env bash
# Creates and deletes only its own uniquely named test containers and data volume.
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
PROJECT="ai-interview-smoke-$$"
CLIENT_CONFIG=""

# The fixture uses only public images. For a local engine, an isolated client
# also keeps this test independent of desktop login/credential-helper state.
endpoint=${DOCKER_HOST:-}
if [ -z "$endpoint" ] || [ -n "${DOCKER_CONTEXT:-}" ]; then
  endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
fi
case "$endpoint" in
  unix://*)
    original_config=${DOCKER_CONFIG:-"$HOME/.docker"}
    CLIENT_CONFIG=$(mktemp -d "${TMPDIR:-/tmp}/ai-interview-smoke-client.XXXXXX")
    printf '{}\n' > "$CLIENT_CONFIG/config.json"
    if [ -d "$original_config/cli-plugins" ]; then
      ln -s "$original_config/cli-plugins" "$CLIENT_CONFIG/cli-plugins"
    fi
    export DOCKER_CONFIG="$CLIENT_CONFIG" DOCKER_HOST="$endpoint"
    unset DOCKER_CONTEXT
    ;;
esac

compose() {
  APP_PORT=0 docker compose --project-directory "$ROOT" --env-file /dev/null \
    -p "$PROJECT" -f "$ROOT/compose.yaml" -f "$ROOT/tests/docker/compose.test.yaml" "$@"
}
cleanup() {
  result=$?
  trap - EXIT
  if [ "$result" -ne 0 ]; then compose logs --tail=60 || true; fi
  compose down --volumes --remove-orphans || result=1
  if [ -n "$CLIENT_CONFIG" ]; then rm -rf -- "$CLIENT_CONFIG"; fi
  exit "$result"
}
trap cleanup EXIT
compose up --build --wait --wait-timeout 120
compose exec -T backend python - initial < "$ROOT/tests/docker/smoke.py"
compose up --no-deps --force-recreate --wait --wait-timeout 120 backend
compose exec -T backend python - persisted < "$ROOT/tests/docker/smoke.py"
printf 'Docker 烟测通过：HTTP、SSE、上传边界、后端重建与文件持久化。\n'
