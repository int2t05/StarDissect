#!/usr/bin/env bash
# 一键同步部署:推送 GitHub → 服务器拉取 → 前端构建 → 重启服务 → 健康检查
# 用法:bash scripts/deploy.sh(在本机仓库根运行;要求改动已 commit)
set -e

cd "$(dirname "$0")/.."

if [ -n "$(git status --short)" ]; then
  echo "✗ 工作区有未提交改动,先 commit 再部署"
  exit 1
fi

git push -q origin main
echo "✓ 已推送 origin/main"

ssh int2t@192.168.2.172 '
  set -e
  cd ~/apps/StarDissect
  for i in 1 2 3; do git pull -q origin main 2>/dev/null && break; sleep 5; done
  echo "✓ 服务器代码: $(git log --oneline -1)"
  cd web && npm run build >/dev/null && echo "✓ 前端已构建"
  cd ..
  systemctl --user restart stardissect
  sleep 3
  systemctl --user is-active stardissect
  curl -sf http://127.0.0.1:8000/healthz && echo " ✓ 服务健康"
'
echo "✓ 部署完成"
