# -*- coding: utf-8 -*-
"""把本 skill 复制到某个项目（或全局 opencode 配置目录）。

用法：
    python install.py --to "C:/path/to/project"          # 装到 <project>/.opencode/skills/logisim
    python install.py --to "%USERPROFILE%/.config/opencode"  # 全局
    python install.py --to <dir> --force                 # 覆盖已有同名 skill

复制时跳过 java/classes（编译产物，目标机器上用 build-tools 重新生成）和 __pycache__。
"""
from __future__ import annotations

import argparse
import shutil
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.abspath(os.path.join(HERE, ".."))
NAME = "logisim"
SKIP_DIRS = {"classes", "__pycache__", ".git"}


def copytree(src, dst):
    os.makedirs(dst, exist_ok=True)
    for entry in os.scandir(src):
        if entry.is_dir():
            if entry.name in SKIP_DIRS:
                continue
            copytree(entry.path, os.path.join(dst, entry.name))
        else:
            if entry.name.endswith(".pyc"):
                continue
            shutil.copy2(entry.path, os.path.join(dst, entry.name))


def main():
    ap = argparse.ArgumentParser(description="安装 logisim skill")
    ap.add_argument("--to", required=True,
                    help="目标项目目录，或 opencode 配置目录（会自动补 .opencode/skills）")
    ap.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    args = ap.parse_args()

    base = os.path.abspath(os.path.expanduser(args.to))
    if os.path.basename(base) in ("skills", ".opencode"):
        dst = os.path.join(base, NAME) if os.path.basename(base) == "skills" \
            else os.path.join(base, "skills", NAME)
    elif os.path.isdir(os.path.join(base, ".opencode")):
        dst = os.path.join(base, ".opencode", "skills", NAME)
    elif os.path.basename(base) == "opencode":
        dst = os.path.join(base, "skills", NAME)
    else:
        dst = os.path.join(base, ".opencode", "skills", NAME)

    if os.path.exists(dst):
        if not args.force:
            raise SystemExit("目标已存在：%s\n加 --force 覆盖（会先删掉旧目录）。" % dst)
        shutil.rmtree(dst)

    copytree(SKILL, dst)
    print("已安装到：%s" % dst)
    print()
    print("下一步：")
    print('  cd "%s"' % dst)
    print("  python scripts/logisim.py env")
    print("  python scripts/logisim.py build-tools")
    print()
    print("Logisim 找不到时设环境变量 LOGISIM_EXE / LOGISIM_JAVA，")
    print("或不设，直接让 logisim.py 自己找（会扫常见安装目录）。")


if __name__ == "__main__":
    main()
