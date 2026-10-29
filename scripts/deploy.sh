#!/usr/bin/env bash
# Local deployment workflow. Only Bash, Docker and standard shell tools required.
set -euo pipefail

ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
CONFIG=${AI_INTERVIEW_ENV_FILE:-"$ROOT/.env"}
case "$CONFIG" in /*) ;; *) CONFIG="$ROOT/$CONFIG" ;; esac
ACTION=${1:-up}

usage() {
  cat <<'EOF'
用法：./scripts/deploy.sh [up|init|doctor|status|logs|stop|down|url]
  up      检查配置、构建并启动，等待服务健康（默认）
  init    首次创建 .env；保留已有配置
  doctor  检查 Docker、Compose、配置和引擎
  status  查看容器状态
  logs    持续查看最近 100 行日志（Ctrl-C 退出）
  stop    停止容器，保留容器与数据
  down    移除容器和网络，保留数据卷
  url     输出当前运行服务的访问地址
可用 AI_INTERVIEW_ENV_FILE 指定配置文件；相对路径按仓库根目录解析。
EOF
}

case "$ACTION" in
  up|init|doctor|status|logs|stop|down|url) ;;
  -h|--help|help) usage; exit 0 ;;
  *) usage >&2; exit 2 ;;
esac
if [ "$#" -gt 1 ]; then usage >&2; exit 2; fi

initialize() {
  if [ -e "$CONFIG" ]; then
    return
  fi
  # noclobber prevents a concurrent init from replacing an existing file.
  (umask 077; set -C; cat "$ROOT/env.example" > "$CONFIG")
  printf '已创建配置：%s\n请填写 API_KEY、BASE_URL、MODEL_NAME，然后再次启动。\n' "$CONFIG"
}

if [ "$ACTION" = init ]; then
  initialize
  printf '配置文件：%s（已有内容不会覆盖）\n' "$CONFIG"
  exit 0
fi
if [ "$ACTION" = up ]; then initialize; fi

if ! command -v docker >/dev/null 2>&1; then
  printf '未找到 Docker。请安装并启动 Docker Desktop，或 Docker Engine + Compose。\n' >&2
  exit 1
fi
if ! version=$(docker compose version --short 2>/dev/null); then
  printf '未找到 Docker Compose。需要 Compose v2.24+ 或 v5。\n' >&2
  exit 1
fi
version=${version#v}
IFS=. read -r major minor rest <<< "$version"
if ! [[ "$major" =~ ^[0-9]+$ && "$minor" =~ ^[0-9]+$ ]] \
  || (( major < 2 || (major == 2 && minor < 24) )); then
  printf 'Compose 版本过旧或无法识别：%s；需要 v2.24+。\n' "$version" >&2
  exit 1
fi

compose() {
  local env_path=/dev/null
  if [ -f "$CONFIG" ]; then env_path=$CONFIG; fi
  docker compose --project-directory "$ROOT" --env-file "$env_path" -f "$ROOT/compose.yaml" "$@"
}

validate_config() {
  if ! compose config --quiet; then
    printf 'Compose 配置无效，请检查 %s 中的 APP_PORT 等字段。\n' "$CONFIG" >&2
    return 2
  fi
  # Let Compose parse dotenv syntax and shell precedence. Never source .env or
  # print resolved configuration: it may contain secrets or shell-like text.
  local invalid
  invalid=$(compose config --environment | awk '
    BEGIN { required["API_KEY"]=1; required["BASE_URL"]=1; required["MODEL_NAME"]=1 }
    /^[A-Z_]+=/ {
      key=substr($0,1,index($0,"=")-1); value=substr($0,index($0,"=")+1)
      if (key in required && value !~ /^[[:space:]]*$/) {
        if (value !~ /^your_/ && value !~ /^<.*>$/ && value !~ /\.example(\/|$)/) delete required[key]
      }
      if (key=="BASE_URL" && value !~ /^https?:\/\//) bad_url=1
      if (key=="APP_PORT" && (value !~ /^[0-9]+$/ || value+0<1 || value+0>65535)) bad_port=1
    }
    END {
      for (key in required) print key " 未填写或仍为占位值"
      if (bad_url) print "BASE_URL 必须以 http:// 或 https:// 开头"
      if (bad_port) print "APP_PORT 必须为 1 到 65535 的整数"
    }')
  if [ -n "$invalid" ]; then
    printf '配置未完成：\n%s\n请编辑 %s 后重试。\n' "$invalid" "$CONFIG" >&2
    return 2
  fi
}

check_engine() {
  if docker info >/dev/null 2>&1; then return; fi
  if [ "$ACTION" = up ] && [ "$(uname -s)" = Darwin ] && [ -d /Applications/Docker.app ]; then
    printf '正在启动 Docker Desktop，最多等待 60 秒……\n'
    open -a Docker
    local attempt
    for attempt in {1..30}; do
      if docker info >/dev/null 2>&1; then return; fi
      sleep 2
    done
  fi
  printf 'Docker 引擎不可用。请启动 Docker Desktop / Docker 服务，然后重试。\n' >&2
  return 1
}

show_url() {
  local address
  address=$(compose port frontend 8080)
  if [ -z "$address" ]; then
    printf '前端尚未运行。请先执行 ./scripts/deploy.sh up。\n' >&2
    return 1
  fi
  printf 'http://%s\n' "$address"
}

build_images() {
  local anonymous
  anonymous=$(compose config --environment | awk -F= '$1=="AI_INTERVIEW_ANONYMOUS_BUILD" {print $2}')
  if [ "$anonymous" != 1 ]; then
    # Local images do not need a new provenance manifest on every cached build:
    # keeping their digest stable avoids resetting in-memory sessions on `up`.
    BUILDX_NO_DEFAULT_ATTESTATIONS=1 compose build
    return
  fi
  # Optional workaround for a blocked desktop credential helper. These base
  # images are public. Isolate only the build client, preserving engine/data.
  local endpoint original_config scratch
  if [ -n "${DOCKER_HOST:-}" ] && [ -z "${DOCKER_CONTEXT:-}" ]; then
    endpoint=$DOCKER_HOST
  else
    endpoint=$(docker context inspect --format '{{.Endpoints.docker.Host}}')
  fi
  case "$endpoint" in
    unix://*) ;;
    *) printf '匿名构建仅支持本机 Unix socket；请取消 AI_INTERVIEW_ANONYMOUS_BUILD。\n' >&2; return 1 ;;
  esac
  original_config=${DOCKER_CONFIG:-"$HOME/.docker"}
  scratch=$(mktemp -d "${TMPDIR:-/tmp}/ai-interview-build.XXXXXX")
  (
    trap 'rm -rf -- "$scratch"' EXIT
    printf '{}\n' > "$scratch/config.json"
    if [ -d "$original_config/cli-plugins" ]; then
      ln -s "$original_config/cli-plugins" "$scratch/cli-plugins"
    fi
    export DOCKER_CONFIG="$scratch" DOCKER_HOST="$endpoint" BUILDX_NO_DEFAULT_ATTESTATIONS=1
    unset DOCKER_CONTEXT
    compose build
  )
}

case "$ACTION" in
  up)
    validate_config
    check_engine
    printf '构建并启动服务，首次运行需要下载镜像和依赖……\n'
    if ! build_images || ! compose up --no-build --wait --wait-timeout 120; then
      printf '\n部署未完成。容器与数据保留，可运行以下命令排查：\n  ./scripts/deploy.sh status\n  ./scripts/deploy.sh logs\n' >&2
      exit 1
    fi
    printf '\n服务已就绪：'
    show_url
    printf '停止：./scripts/deploy.sh down（保留数据）\n'
    ;;
  doctor)
    validate_config
    check_engine
    printf 'Docker、Compose 和部署配置检查通过；尚未验证模型供应商。\n'
    ;;
  status) check_engine; compose ps --all ;;
  logs) check_engine; compose logs --tail=100 --follow ;;
  stop) check_engine; compose stop ;;
  down) check_engine; compose down ;;
  url) check_engine; show_url ;;
esac
