from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    repo_root = Path(os.environ.get("LLAMA_FACTORY_ROOT", "D:/Program/LLaMA-Factory")).resolve()
    src_dir = repo_root / "src"
    if not src_dir.is_dir():
        raise FileNotFoundError(f"LLaMA-Factory src not found: {src_dir}")

    sys.path.insert(0, str(src_dir))

    from llamafactory.extras.misc import fix_proxy, is_env_enabled
    from llamafactory.webui.interface import create_ui

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
