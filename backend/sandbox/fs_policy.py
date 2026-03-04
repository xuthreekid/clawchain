"""文件系统安全策略 — 路径验证、事务性写入、增强 LangChain 的 root_dir"""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Sequence

BLOCKED_SYSTEM_DIRS = {
    "/etc", "/proc", "/sys", "/dev", "/boot", "/run",
    "/root", "/var/run", "/sbin", "/usr/sbin",
}

PROTECTED_EXTENSIONS = {
    ".env", ".pem", ".key", ".p12", ".pfx", ".jks",
}


class PathSecurityError(Exception):
    pass


def _check_blocked(target: Path) -> None:
    target_str = str(target)
    for blocked in BLOCKED_SYSTEM_DIRS:
        if target_str == blocked or target_str.startswith(blocked + "/"):
            raise PathSecurityError(f"禁止访问系统目录: {blocked}")


def validate_path(path: str, root_dir: str) -> Path:
    """
    验证并规范化路径，确保不逃逸出 root_dir。
    返回 resolve 后的绝对路径。
    """
    root = Path(root_dir).resolve()
    if not root.exists():
        raise PathSecurityError(f"根目录不存在: {root}")

    target = (root / path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise PathSecurityError(
            f"路径 '{path}' 逃逸出了工作区边界 '{root}'"
        )

    _check_blocked(target)
    return target


def validate_path_for_fs(
    path: str,
    root_dir: str,
    readonly_dirs: Sequence[str],
    project_root: Path,
    is_write: bool,
) -> Path:
    """
    文件工具路径验证：支持 readonly_dirs 只读白名单。
    - readonly_dirs：相对于 project_root 的目录列表（如 ["docs"]）
    - 若路径落在白名单内且 is_write=True：拒绝
    - 若路径落在白名单内且 is_write=False：放行（可读工作区外）
    - 否则走常规 workspace 边界校验
    """
    if not readonly_dirs:
        if is_write:
            return validate_path_relaxed(path, root_dir)
        return validate_path(path, root_dir)

    # 尝试解析为 project_root 下的白名单路径
    clean = path.strip().replace("\\", "/").lstrip("/")
    for rd in readonly_dirs:
        rd_clean = rd.strip().replace("\\", "/").rstrip("/")
        if not rd_clean:
            continue
        if clean == rd_clean or clean.startswith(rd_clean + "/"):
            target = (project_root / clean).resolve()
            try:
                target.relative_to(project_root.resolve())
            except ValueError:
                raise PathSecurityError(f"路径 '{path}' 逃逸出项目根")
            _check_blocked(target)
            if is_write:
                raise PathSecurityError(f"路径 '{path}' 在只读白名单内，禁止写入")
            if not target.exists():
                raise PathSecurityError(f"路径不存在: '{path}'")
            return target

    # 非白名单路径：写操作用 relaxed（允许创建新文件），读操作用严格校验
    if is_write:
        return validate_path_relaxed(path, root_dir)
    return validate_path(path, root_dir)


def validate_path_relaxed(path: str, root_dir: str) -> Path:
    """
    宽松路径验证 — 允许路径不存在（用于 write 创建新文件），
    但仍检查边界。
    """
    root = Path(root_dir).resolve()

    if Path(path).is_absolute():
        target = Path(path).resolve()
    else:
        target = (root / path).resolve()

    try:
        target.relative_to(root)
    except ValueError:
        raise PathSecurityError(
            f"路径 '{path}' 逃逸出了工作区边界 '{root}'"
        )

    _check_blocked(target)
    return target


def is_protected_file(path: Path) -> bool:
    """检查是否为受保护文件（密钥、证书等）"""
    return path.suffix.lower() in PROTECTED_EXTENSIONS


def write_atomic(path: Path, content: str, encoding: str = "utf-8") -> None:
    """事务性写入：先写 .tmp 再 rename，写入中断不损坏原文件"""
    tmp_path = path.with_suffix(path.suffix + ".clw_tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_text(content, encoding=encoding)
        shutil.move(str(tmp_path), str(path))
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise
