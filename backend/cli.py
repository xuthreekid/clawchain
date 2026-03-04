"""ClawChain CLI — setup / onboard / config / doctor / serve / start

Usage:
    python cli.py setup          从模板创建数据目录与配置文件
    python cli.py onboard        交互式初始化向导（Provider/模型/密钥）
    python cli.py config show    显示当前配置（脱敏）
    python cli.py config set KEY VALUE   设置配置项
    python cli.py doctor         诊断与发布态检查
    python cli.py serve          启动后端服务（支持 CLI 初始化或前端初始化）
    python cli.py start          一键启动（自动 setup + 快速配置 + serve）
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

PROVIDER_TEMPLATES = {
    "openai": {
        "baseUrl": "https://api.openai.com/v1",
        "api": "openai-completions",
        "models": [
            {"id": "gpt-4o", "name": "GPT-4o", "contextWindow": 128000, "maxTokens": 16384, "reasoning": False, "input": ["text", "image"]},
            {"id": "gpt-4o-mini", "name": "GPT-4o Mini", "contextWindow": 128000, "maxTokens": 16384, "reasoning": False, "input": ["text"]},
        ],
    },
    "anthropic": {
        "baseUrl": "https://api.anthropic.com",
        "api": "anthropic-messages",
        "models": [
            {"id": "claude-sonnet-4-20250514", "name": "Claude Sonnet 4", "contextWindow": 200000, "maxTokens": 8192, "reasoning": True, "input": ["text", "image"]},
            {"id": "claude-3-5-haiku-20241022", "name": "Claude 3.5 Haiku", "contextWindow": 200000, "maxTokens": 8192, "reasoning": False, "input": ["text"]},
        ],
    },
    "deepseek": {
        "baseUrl": "https://api.deepseek.com",
        "api": "openai-completions",
        "models": [
            {"id": "deepseek-chat", "name": "DeepSeek Chat", "contextWindow": 128000, "maxTokens": 8192, "reasoning": False, "input": ["text"]},
            {"id": "deepseek-reasoner", "name": "DeepSeek Reasoner", "contextWindow": 128000, "maxTokens": 8192, "reasoning": True, "input": ["text"]},
        ],
    },
    "openrouter": {
        "baseUrl": "https://openrouter.ai/api/v1",
        "api": "openai-completions",
        "models": [
            {"id": "openai/gpt-4o", "name": "GPT-4o (OpenRouter)", "contextWindow": 128000, "maxTokens": 16384, "reasoning": False, "input": ["text"]},
        ],
    },
    "ollama": {
        "baseUrl": "http://localhost:11434",
        "api": "ollama",
        "models": [
            {"id": "llama3.1", "name": "Llama 3.1", "contextWindow": 128000, "maxTokens": 8192, "reasoning": False, "input": ["text"]},
        ],
    },
}


UI_WIDTH = 64


def _print_title(title: str) -> None:
    bar = "=" * UI_WIDTH
    print(f"\n{bar}\n{title}\n{bar}")


def _print_section(title: str) -> None:
    print(f"\n[{title}]")


def _print_status(level: str, message: str) -> None:
    print(f"[{level}] {message}")


def _ask_yes_no(prompt: str, *, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    raw = input(f"{prompt} ({hint}): ").strip().lower()
    if not raw:
        return default
    return raw in {"y", "yes"}


def _ask_text(prompt: str, *, default: str | None = None) -> str:
    if default is not None:
        raw = input(f"{prompt} [{default}]: ").strip()
        return raw or default
    return input(f"{prompt}: ").strip()


def _choose_from_options(prompt: str, options: list[str], *, default_index: int = 1) -> str:
    """Prompt user to choose from numbered options."""
    if not options:
        return ""
    if default_index < 1 or default_index > len(options):
        default_index = 1
    while True:
        for i, opt in enumerate(options, 1):
            print(f"    {i}. {opt}")
        raw = input(f"{prompt} (默认{default_index}): ").strip()
        if not raw:
            return options[default_index - 1]
        try:
            idx = int(raw)
            if 1 <= idx <= len(options):
                return options[idx - 1]
        except ValueError:
            pass
        print("  输入无效，请输入编号。")


def _apply_provider_template(
    cfg: dict,
    *,
    provider_name: str,
    model_id: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
) -> str:
    if provider_name not in PROVIDER_TEMPLATES:
        raise ValueError(f"不支持的 provider: {provider_name}")

    template = PROVIDER_TEMPLATES[provider_name]
    models = template.get("models", [])
    final_model_id = model_id or (models[0]["id"] if models else "")
    final_base_url = base_url or template.get("baseUrl")
    provider_cfg = {
        "baseUrl": final_base_url,
        "api": template["api"],
        "models": models,
    }
    if api_key:
        provider_cfg["apiKey"] = api_key

    cfg.setdefault("models", {}).setdefault("providers", {})[provider_name] = provider_cfg
    default_model = f"{provider_name}/{final_model_id}" if final_model_id else ""
    if default_model:
        cfg.setdefault("agents", {}).setdefault("defaults", {})["model"] = default_model
    return default_model


def _is_config_ready(cfg: dict) -> bool:
    providers = cfg.get("models", {}).get("providers", {})
    model = cfg.get("agents", {}).get("defaults", {}).get("model")
    return bool(providers) and bool(model)


def cmd_setup(args: argparse.Namespace) -> None:
    from config import DATA_DIR, _config_path, TEMPLATE_PATH

    _print_title("ClawChain Setup")
    _print_status("INFO", f"数据目录: {DATA_DIR}")
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    config_path = _config_path()
    if config_path.exists() and not args.force:
        _print_status("INFO", f"配置文件已存在: {config_path}")
        _print_status("INFO", "使用 --force 可重新从模板生成")
    else:
        if TEMPLATE_PATH.exists():
            shutil.copy2(str(TEMPLATE_PATH), str(config_path))
            _print_status("OK", f"已从模板创建配置: {config_path}")
        else:
            from config import load_config
            load_config()
            _print_status("OK", f"已创建默认配置: {config_path}")

    from config import load_config
    from graph.workspace import ensure_agent_workspace
    cfg = load_config()

    agents_list = cfg.get("agents", {}).get("list", [])
    for agent in agents_list:
        agent_id = agent["id"]
        agent_dir = ensure_agent_workspace(agent_id)
        _print_status("OK", f"Agent '{agent_id}' workspace: {agent_dir}")

    # Ensure default skill-creator exists
    skills_dir = DATA_DIR / "skills" / "skill-creator"
    if skills_dir.exists():
        _print_status("OK", "默认 skill 'skill-creator' 已就绪")
    else:
        _print_status("WARN", "默认 skill 'skill-creator' 不存在，请确保 data/skills/skill-creator/SKILL.md 已包含")

    _print_status("OK", "setup 完成")
    _print_status("INFO", "下一步: python cli.py onboard")


def cmd_onboard(args: argparse.Namespace) -> None:
    from config import get_raw_config, load_config, save_config, _config_path, is_initialized
    from graph.workspace import ensure_agent_workspace

    if not is_initialized():
        _print_status("INFO", "配置文件不存在，先运行 setup...")
        cmd_setup(argparse.Namespace(force=False))

    load_config()
    cfg = get_raw_config()
    _print_title("ClawChain Onboard Wizard")

    # 1. Provider / Model
    _print_section("1/3 Provider 配置")
    providers = cfg.get("models", {}).get("providers", {})
    if providers:
        _print_status("INFO", f"已配置 {len(providers)} 个 Provider: {', '.join(providers.keys())}")
        add_more = _ask_yes_no("是否添加新 Provider？", default=False)
    else:
        _print_status("INFO", "当前未配置任何 Provider。")
        add_more = True

    if add_more:
        _print_status("INFO", "可选 Provider 模板:")
        templates = list(PROVIDER_TEMPLATES.keys())
        for i, name in enumerate(templates, 1):
            t = PROVIDER_TEMPLATES[name]
            model_names = ", ".join(m["name"] for m in t["models"][:3])
            print(f"    {i}. {name} ({model_names})")
        print(f"    {len(templates) + 1}. 自定义 (手动输入)")

        choice = input(f"  选择 (1-{len(templates) + 1}): ").strip()
        try:
            idx = int(choice)
        except ValueError:
            idx = 0

        if 1 <= idx <= len(templates):
            provider_name = templates[idx - 1]
            template = PROVIDER_TEMPLATES[provider_name]
            _print_status("OK", f"已选择: {provider_name}")

            api_key = _ask_text(f"{provider_name} API Key", default="")

            provider_cfg = {
                "baseUrl": template["baseUrl"],
                "api": template["api"],
                "models": template["models"],
            }
            if api_key:
                provider_cfg["apiKey"] = api_key

            cfg.setdefault("models", {}).setdefault("providers", {})[provider_name] = provider_cfg

            default_model = f"{provider_name}/{template['models'][0]['id']}"
            cfg.setdefault("agents", {}).setdefault("defaults", {})["model"] = default_model
            _print_status("OK", f"默认模型已设为: {default_model}")

        elif idx == len(templates) + 1:
            provider_name = _ask_text("Provider 名称")
            if provider_name:
                base_url = _ask_text("API Base URL", default="")
                api_key = _ask_text("API Key", default="")
                model_id = _ask_text("模型 ID")
                model_name = _ask_text("模型显示名", default=model_id)
                _print_status("INFO", "API 协议选择:")
                api_protocol = _choose_from_options(
                    "  请选择协议编号",
                    ["openai-completions", "anthropic-messages", "ollama"],
                    default_index=1,
                )

                provider_cfg = {
                    "baseUrl": base_url or None,
                    "api": api_protocol,
                    "models": [{"id": model_id, "name": model_name}] if model_id else [],
                }
                if api_key:
                    provider_cfg["apiKey"] = api_key
                cfg.setdefault("models", {}).setdefault("providers", {})[provider_name] = provider_cfg

                if model_id:
                    cfg.setdefault("agents", {}).setdefault("defaults", {})["model"] = f"{provider_name}/{model_id}"
                    _print_status("OK", f"默认模型已设为: {provider_name}/{model_id}")

    # 2. Heartbeat
    _print_section("2/3 心跳配置")
    hb = cfg.get("agents", {}).get("defaults", {}).get("heartbeat", {})
    hb_enabled = hb.get("enabled", False)
    enable_hb = _ask_yes_no(f"启用心跳？(当前: {'是' if hb_enabled else '否'})", default=False)
    if enable_hb:
        cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("heartbeat", {})["enabled"] = True
        new_every = _ask_text("心跳间隔", default=str(hb.get("every", "30m"))).strip()
        if new_every:
            cfg["agents"]["defaults"]["heartbeat"]["every"] = new_every
    else:
        cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("heartbeat", {})["enabled"] = False

    # 3. Timezone
    _print_section("3/3 用户时区")
    current_tz = cfg.get("agents", {}).get("defaults", {}).get("user_timezone", "Asia/Shanghai")
    new_tz = _ask_text("时区", default=current_tz).strip()
    if new_tz:
        cfg.setdefault("agents", {}).setdefault("defaults", {})["user_timezone"] = new_tz

    save_config(cfg, validate=False)
    ensure_agent_workspace("main")

    _print_status("OK", f"配置已保存到: {_config_path()}")
    _print_status("OK", "onboard 完成")
    _print_status("INFO", "运行 `python cli.py start` 或 `python cli.py serve` 启动服务。")


def cmd_config_show(args: argparse.Namespace) -> None:
    from config import load_config
    from config_schema import sanitize_config_for_client
    cfg = load_config()
    sanitized = sanitize_config_for_client(cfg)
    print(json.dumps(sanitized, ensure_ascii=False, indent=2))


def cmd_config_set(args: argparse.Namespace) -> None:
    from config import get_raw_config, load_config, save_config

    load_config()
    cfg = get_raw_config()
    parts = args.key.split(".")
    current = cfg
    for p in parts[:-1]:
        current = current.setdefault(p, {})

    value = args.value
    if value.lower() in ("true", "false"):
        value = value.lower() == "true"
    elif value.isdigit():
        value = int(value)
    else:
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, ValueError):
            pass

    current[parts[-1]] = value
    save_config(cfg)
    print(f"[config] 已设置 {args.key} = {value}")


def cmd_doctor(args: argparse.Namespace) -> None:
    from config import load_config, _config_path, DATA_DIR, TEMPLATE_PATH, is_initialized
    from config_schema import validate_config

    _print_title("ClawChain Doctor")
    issues = []

    # 1. 初始化状态
    if is_initialized():
        _print_status("OK", f"配置文件存在: {_config_path()}")
    else:
        _print_status("WARN", f"配置文件不存在: {_config_path()}")
        issues.append("运行 `python cli.py setup` 创建配置")

    # 2. 模板文件
    if TEMPLATE_PATH.exists():
        _print_status("OK", f"配置模板存在: {TEMPLATE_PATH}")
    else:
        _print_status("WARN", f"配置模板缺失: {TEMPLATE_PATH}")
        issues.append("config.template.json 缺失")

    # 3. Schema 校验
    if is_initialized():
        cfg = load_config()
        result = validate_config(cfg)
        if result.ok:
            _print_status("OK", "配置 Schema 校验通过")
        else:
            for err in result.errors:
                _print_status("ERROR", f"Schema: {err}")
                issues.append(f"配置错误: {err}")
    else:
        cfg = {}

    # 4. Provider 检查
    providers = cfg.get("models", {}).get("providers", {})
    if providers:
        for name, p in providers.items():
            models_list = p.get("models", [])
            has_key = bool(p.get("apiKey")) and "***" not in str(p.get("apiKey", ""))
            has_url = bool(p.get("baseUrl"))
            status = "[OK]" if (has_url and models_list) else "[WARN]"
            print(f"{status} Provider '{name}': {len(models_list)} 模型, baseUrl={'有' if has_url else '缺'}, apiKey={'已配置' if has_key else '未配置'}")
            if not has_key:
                issues.append(f"Provider '{name}' 缺少 apiKey")
            if not has_url:
                issues.append(f"Provider '{name}' 缺少 baseUrl")
    else:
        _print_status("WARN", "未配置任何 Provider")
        issues.append("运行 `python cli.py onboard` 配置模型")

    # 5. 默认模型
    default_model = cfg.get("agents", {}).get("defaults", {}).get("model")
    if default_model:
        _print_status("OK", f"默认模型: {default_model}")
    else:
        _print_status("WARN", "未设置默认模型 (agents.defaults.model)")
        issues.append("设置默认模型: python cli.py config set agents.defaults.model provider/model")

    # 6. Agent workspace
    agents_list = cfg.get("agents", {}).get("list", [])
    for agent in agents_list:
        ws = DATA_DIR / "agents" / agent["id"] / "workspace"
        if ws.exists():
            _print_status("OK", f"Agent '{agent['id']}' workspace 存在")
        else:
            _print_status("WARN", f"Agent '{agent['id']}' workspace 不存在")
            issues.append(f"Agent '{agent['id']}' workspace 缺失，运行 `python cli.py setup`")

    # 7. 默认 Skills
    skill_creator = DATA_DIR / "skills" / "skill-creator" / "SKILL.md"
    if skill_creator.exists():
        _print_status("OK", "默认 skill 'skill-creator' 存在")
    else:
        _print_status("WARN", "默认 skill 'skill-creator' 缺失")
        issues.append("data/skills/skill-creator/SKILL.md 缺失")

    # 8. .gitignore 检查（发布态）
    root_dir = Path(__file__).resolve().parent.parent
    gitignore = root_dir / ".gitignore"
    if gitignore.exists():
        _print_status("OK", ".gitignore 存在")
    else:
        _print_status("WARN", ".gitignore 缺失")
        issues.append("添加 .gitignore")

    # 9. 敏感信息检查
    config_path = _config_path()
    if config_path.exists():
        with open(config_path, "r") as f:
            content = f.read()
        if "sk-" in content and "***" not in content:
            _print_status("WARN", "config.json 可能包含明文 API Key")
            issues.append("config.json 含明文密钥，请清理或使用 ${ENV_VAR} 引用")
        else:
            _print_status("OK", "config.json 无明文密钥泄露")

    # 10. 端口检查
    for port in [8002, 3000]:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(("localhost", port))
                if result == 0:
                    _print_status("INFO", f"端口 {port} 已被占用")
                else:
                    _print_status("OK", f"端口 {port} 可用")
        except Exception:
            _print_status("OK", f"端口 {port} 可用")

    # 11. Python 依赖
    try:
        import fastapi
        import langchain_core
        import langgraph
        _print_status("OK", "核心 Python 依赖已安装")
    except ImportError as e:
        _print_status("ERROR", f"缺少依赖: {e}")
        issues.append("安装依赖: pip install -r requirements.txt")

    print()
    if issues:
        _print_status("WARN", f"发现 {len(issues)} 个问题:")
        for i, issue in enumerate(issues, 1):
            print(f"  {i}. {issue}")
    else:
        _print_status("OK", "一切正常！运行 `python cli.py start` 或 `python cli.py serve` 启动服务。")


def cmd_serve(args: argparse.Namespace) -> None:
    from config import is_initialized

    if not is_initialized():
        if args.require_init:
            print("[serve] 未初始化！请先运行:")
            print("  python cli.py setup")
            print("  python cli.py onboard")
            sys.exit(1)
        print("[serve] 检测到尚未初始化，已启用前端初始化路径。")
        print("  你可以在启动后通过 Web 配置中心完成 Provider/模型配置。")
        print("  （如需强制 CLI 初始化，请使用: python cli.py serve --require-init）")

    import uvicorn
    host = args.host or "0.0.0.0"
    port = args.port or 8002

    if args.sidecar:
        host = "127.0.0.1"
        port = 3716
        print(f"[serve] Sidecar 模式: http://{host}:{port}")
    else:
        print(f"[serve] 启动 ClawChain 后端: http://{host}:{port}")

    uvicorn.run("app:app", host=host, port=port, reload=args.reload and not args.sidecar)


def cmd_start(args: argparse.Namespace) -> None:
    """One-command startup: setup + quick config + serve."""
    from config import get_raw_config, is_initialized, load_config, save_config
    from graph.workspace import ensure_agent_workspace

    if not is_initialized():
        _print_status("INFO", "未检测到初始化配置，正在执行 setup...")
        cmd_setup(argparse.Namespace(force=False))

    load_config()
    cfg = get_raw_config()

    if not _is_config_ready(cfg):
        if args.onboard:
            _print_status("INFO", "配置未完成，进入完整交互向导...")
            cmd_onboard(argparse.Namespace())
            load_config()
            cfg = get_raw_config()
        else:
            provider_name = args.provider
            if not provider_name:
                if sys.stdin.isatty():
                    _print_status("INFO", "未完成模型配置，进入快速配置。")
                    _print_status("INFO", "可选 provider: " + ", ".join(PROVIDER_TEMPLATES.keys()))
                    provider_name = input("  provider [deepseek]: ").strip() or "deepseek"
                else:
                    provider_name = "deepseek"

            if provider_name not in PROVIDER_TEMPLATES:
                _print_status("ERROR", f"无效 provider: {provider_name}")
                _print_status("INFO", f"可选: {', '.join(PROVIDER_TEMPLATES.keys())}")
                sys.exit(1)

            api_key = args.api_key
            if not api_key and sys.stdin.isatty():
                api_key = input(f"  {provider_name} API Key（可回车跳过）: ").strip() or None

            model_id = args.model
            if not model_id and sys.stdin.isatty():
                template_models = PROVIDER_TEMPLATES[provider_name].get("models", [])
                if template_models:
                    _print_status("INFO", "可选模型:")
                    for i, m in enumerate(template_models, 1):
                        print(f"    {i}. {m.get('id')}")
                    choice = input("  选择模型编号（默认1）: ").strip()
                    try:
                        idx = int(choice) if choice else 1
                        if 1 <= idx <= len(template_models):
                            model_id = template_models[idx - 1].get("id")
                    except ValueError:
                        model_id = template_models[0].get("id")

            default_model = _apply_provider_template(
                cfg,
                provider_name=provider_name,
                model_id=model_id,
                api_key=api_key,
                base_url=args.base_url,
            )

            if args.user_timezone:
                cfg.setdefault("agents", {}).setdefault("defaults", {})["user_timezone"] = args.user_timezone
            if args.heartbeat_every:
                hb = cfg.setdefault("agents", {}).setdefault("defaults", {}).setdefault("heartbeat", {})
                hb["enabled"] = True
                hb["every"] = args.heartbeat_every

            save_config(cfg, validate=False)
            ensure_agent_workspace("main")
            _print_status("OK", f"快速配置完成，默认模型: {default_model or '(未设置)'}")

    if args.doctor:
        _print_status("INFO", "执行启动前检查...")
        cmd_doctor(argparse.Namespace())

    _print_status("INFO", "启动服务...")
    cmd_serve(
        argparse.Namespace(
            host=args.host,
            port=args.port,
            reload=args.reload,
            require_init=False,
            sidecar=args.sidecar,
        )
    )


def cmd_clean(args: argparse.Namespace) -> None:
    """Clean runtime/build artifacts."""
    from config import DATA_DIR, _config_path

    backend_dir = Path(__file__).resolve().parent
    root_dir = backend_dir.parent
    removed: list[str] = []

    def _rm(path: Path) -> None:
        if not path.exists():
            return
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
        removed.append(str(path))

    # Always-safe runtime/cache cleanup.
    _rm(backend_dir / ".pytest_cache")
    _rm(backend_dir / "__pycache__")
    _rm(root_dir / "desktop" / "node_modules")
    _rm(root_dir / "desktop" / "src-tauri" / "target")
    _rm(root_dir / "frontend" / ".next")
    _rm(root_dir / "frontend" / "out")

    # Deep data cleanup mode.
    if args.clean:
        _rm(DATA_DIR / "agents")
        _rm(DATA_DIR / "subagents")
        _rm(DATA_DIR / "cron")
        _rm(_config_path())

    # Remove pyc under backend.
    for pyc in backend_dir.rglob("*.pyc"):
        try:
            pyc.unlink()
            removed.append(str(pyc))
        except OSError:
            pass

    mode = "deep" if args.clean else "runtime"
    _print_title("ClawChain Clean")
    _print_status("INFO", f"清理模式: {mode}")
    if removed:
        _print_status("OK", f"已清理 {len(removed)} 项")
        if args.verbose:
            for p in removed:
                print(f"  - {p}")
        else:
            preview = removed[:8]
            for p in preview:
                print(f"  - {p}")
            remain = len(removed) - len(preview)
            if remain > 0:
                print(f"  ... 其余 {remain} 项可使用 --verbose 查看")
    else:
        _print_status("OK", "无需清理，目录已是干净状态。")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="clawchain",
        description="ClawChain CLI",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python cli.py start\n"
            "  python cli.py start --provider deepseek --api-key sk-xxx --model deepseek-chat\n"
            "  python cli.py clean --clean\n"
            "  python cli.py clean --clean --verbose\n"
        ),
    )
    sub = parser.add_subparsers(dest="command")

    setup_parser = sub.add_parser("setup", help="从模板创建数据目录与配置文件")
    setup_parser.add_argument("--force", action="store_true", help="强制重新生成配置")

    sub.add_parser("onboard", help="交互式初始化向导")
    sub.add_parser("doctor", help="诊断当前环境与配置")

    config_parser = sub.add_parser("config", help="配置管理")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_sub.add_parser("show", help="显示当前配置（脱敏）")
    set_parser = config_sub.add_parser("set", help="设置配置项")
    set_parser.add_argument("key", help="配置键（如 agents.defaults.model）")
    set_parser.add_argument("value", help="配置值")

    serve_parser = sub.add_parser("serve", help="启动后端服务")
    serve_parser.add_argument("--host", default="0.0.0.0")
    serve_parser.add_argument("--port", type=int, default=8002)
    serve_parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="启用热重载（默认开启，可用 --no-reload 关闭）",
    )
    serve_parser.add_argument(
        "--require-init",
        action="store_true",
        help="强制要求先执行 setup/onboard（未初始化时拒绝启动）",
    )
    serve_parser.add_argument(
        "--sidecar",
        action="store_true",
        help="Sidecar 模式（由 Tauri 桌面应用启动，使用 localhost:3716）",
    )

    start_parser = sub.add_parser("start", help="一键启动（自动 setup + 快速配置 + serve）")
    start_parser.add_argument("--host", default="0.0.0.0")
    start_parser.add_argument("--port", type=int, default=8002)
    start_parser.add_argument(
        "--reload",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="启用热重载（默认开启，可用 --no-reload 关闭）",
    )
    start_parser.add_argument("--provider", choices=list(PROVIDER_TEMPLATES.keys()), default=None)
    start_parser.add_argument("--api-key", dest="api_key", default=None, help="Provider API Key")
    start_parser.add_argument("--model", default=None, help="模型 ID（例如 deepseek-chat）")
    start_parser.add_argument("--base-url", dest="base_url", default=None, help="Provider baseUrl 覆盖")
    start_parser.add_argument("--user-timezone", dest="user_timezone", default=None, help="用户时区（例如 Asia/Shanghai）")
    start_parser.add_argument("--heartbeat-every", dest="heartbeat_every", default=None, help="心跳间隔（例如 30m）")
    start_parser.add_argument("--onboard", action="store_true", help="使用完整 onboard 向导而不是快速配置")
    start_parser.add_argument("--doctor", action="store_true", help="启动前执行 doctor 检查")
    start_parser.add_argument("--sidecar", action="store_true", help="Sidecar 模式（127.0.0.1:3716）")

    clean_parser = sub.add_parser("clean", help="清理运行产物/缓存")
    clean_parser.add_argument(
        "--clean",
        action="store_true",
        help="深度清理（额外清理 backend/data 下运行数据与 config.json）",
    )
    clean_parser.add_argument(
        "--verbose",
        action="store_true",
        help="输出完整清理明细",
    )

    args = parser.parse_args()

    if args.command == "setup":
        cmd_setup(args)
    elif args.command == "onboard":
        cmd_onboard(args)
    elif args.command == "doctor":
        cmd_doctor(args)
    elif args.command == "config":
        if args.config_action == "show":
            cmd_config_show(args)
        elif args.config_action == "set":
            cmd_config_set(args)
        else:
            print("用法: python cli.py config {show|set}")
    elif args.command == "serve":
        cmd_serve(args)
    elif args.command == "start":
        cmd_start(args)
    elif args.command == "clean":
        cmd_clean(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
