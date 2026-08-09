#!/bin/zsh

# Double-click launcher for the local portfolio demo.
set -eu

script_dir="$(cd "$(dirname "$0")" && pwd)"
project_dir="$(cd "$script_dir/.." && pwd)"
log_file="$project_dir/.desktop-launch.log"
url="http://127.0.0.1:8000/"

if ! /usr/sbin/lsof -nP -iTCP:8000 -sTCP:LISTEN >/dev/null 2>&1; then
  cd "$project_dir"
  if [[ -x "$project_dir/.venv/bin/python" ]]; then
    "$project_dir/.venv/bin/python" manage.py runserver 127.0.0.1:8000 --noreload \
      >"$log_file" 2>&1 &
  else
    /usr/bin/env uv run python manage.py runserver 127.0.0.1:8000 --noreload \
      >"$log_file" 2>&1 &
  fi
fi

for _ in {1..30}; do
  if /usr/bin/curl --noproxy '*' -fsS "$url" >/dev/null 2>&1; then
    /usr/bin/open -a Safari "$url"
    exit 0
  fi
  /bin/sleep 0.25
done

/usr/bin/osascript -e 'display alert "我拼个豆暂时无法启动" message "本地服务未能在 8 秒内就绪，请查看项目文件夹中的 .desktop-launch.log。"'
exit 1
