from __future__ import annotations

import os
import sys
import traceback
from pathlib import Path


class CompatibilityBlocked(RuntimeError):
    """Raised when the locked health runtime cannot import the full tuning UI."""


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split("+", 1)[0].split(".")
    padded = (parts + ["0", "0", "0"])[:3]
    result: list[int] = []
    for part in padded:
        number = "".join(ch for ch in part if ch.isdigit())
        result.append(int(number or "0"))
    return tuple(result)  # type: ignore[return-value]


def _assert_full_llamafactory_compatible() -> None:
    import torch
    import transformers

    torch_version = _version_tuple(getattr(torch, "__version__", "0.0.0"))
    transformers_version = _version_tuple(getattr(transformers, "__version__", "0.0.0"))
    blockers: list[str] = []
    if torch_version < (2, 4, 0):
        blockers.append(f"torch {torch.__version__} < 2.4.0")
    if transformers_version < (4, 55, 0):
        blockers.append(f"transformers {transformers.__version__} < 4.55.0")
    if blockers:
        raise CompatibilityBlocked("; ".join(blockers))


def _launch_health_compat_console(repo_root: Path, reason: BaseException) -> None:
    import gradio as gr
    import time

    server_name = os.getenv("GRADIO_SERVER_NAME", "0.0.0.0")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))
    python_path = sys.executable

    diagnostic = "\n".join(
        [
            "Health environment compatibility console",
            f"Python: {python_path}",
            f"LLaMA-Factory root: {repo_root}",
            f"Startup fallback reason: {type(reason).__name__}: {reason}",
            "",
            "The current health lock list pins torch==2.2.2 and tokenizers==0.20.3.",
            "The local LLaMA-Factory source requires torch>=2.4 and transformers>=4.55.",
        ]
    )

    def refresh_diagnostics() -> str:
        lines = [diagnostic, "", "Traceback:", traceback.format_exc()]
        return "\n".join(lines)

    def environment_probe() -> str:
        modules = ["torch", "transformers", "tokenizers", "gradio", "datasets", "peft", "trl"]
        rows: list[str] = []
        for name in modules:
            try:
                module = __import__(name)
                rows.append(f"{name}: {getattr(module, '__version__', 'installed')}")
            except Exception as exc:
                rows.append(f"{name}: ERROR {type(exc).__name__}: {exc}")
        return "\n".join(rows)

    with gr.Blocks(title="Health Model Tuning Console") as demo:
        gr.Markdown("## Health Model Tuning Console")
        gr.Markdown(
            "当前 health 环境已按锁定清单启动。完整 LLaMAFactory WebUI 因依赖版本冲突进入兼容模式。"
        )
        gr.Textbox(value=diagnostic, label="Startup diagnostics", lines=10)
        with gr.Row():
            probe_button = gr.Button("Probe environment")
            traceback_button = gr.Button("Show fallback trace")
        output = gr.Textbox(label="Output", lines=14)
        probe_button.click(environment_probe, outputs=output)
        traceback_button.click(refresh_diagnostics, outputs=output)

    print(f"Visit http://{server_name}:{server_port} for model tuning console")
    demo.queue().launch(
        server_name=server_name,
        server_port=server_port,
        inbrowser=False,
        prevent_thread_lock=True,
        show_error=True,
    )

    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return


def main() -> int:
    repo_root = Path(os.environ.get("LLAMA_FACTORY_ROOT", "D:/Program/LLaMA-Factory")).resolve()
    src_dir = repo_root / "src"
    if not src_dir.is_dir():
        raise FileNotFoundError(f"LLaMA-Factory src not found: {src_dir}")

    os.environ.setdefault("DISABLE_VERSION_CHECK", "1")
    sys.path.insert(0, str(src_dir))

    try:
        _assert_full_llamafactory_compatible()
        from llamafactory.extras.misc import fix_proxy, is_env_enabled
        from llamafactory.webui.interface import create_ui
    except BaseException as exc:
        _launch_health_compat_console(repo_root=repo_root, reason=exc)
        return 0

    gradio_ipv6 = is_env_enabled("GRADIO_IPV6")
    gradio_share = is_env_enabled("GRADIO_SHARE")
    server_name = os.getenv("GRADIO_SERVER_NAME", "[::]" if gradio_ipv6 else "0.0.0.0")
    server_port = int(os.getenv("GRADIO_SERVER_PORT", "7860"))

    print(f"Visit http://{server_name}:{server_port} for model tuning console")
    fix_proxy(ipv6_enabled=gradio_ipv6)
    create_ui().queue().launch(
        share=gradio_share,
        server_name=server_name,
        server_port=server_port,
        inbrowser=False,
        prevent_thread_lock=True,
        show_error=True,
    )

    try:
        import time

        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
