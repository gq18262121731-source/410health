# Copyright 2025 the LlamaFactory team.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os
import platform

from ..extras.misc import fix_proxy, is_env_enabled
from ..extras.packages import is_gradio_available
from .common import save_config
from .components import (
    create_chat_box,
    create_eval_tab,
    create_export_tab,
    create_footer,
    create_infer_tab,
    create_top,
    create_train_tab,
)
from .css import CSS
from .engine import Engine
from .locales import LOCALES


if is_gradio_available():
    import gradio as gr


def create_ui(demo_mode: bool = False) -> "gr.Blocks":
    engine = Engine(demo_mode=demo_mode, pure_chat=False)
    hostname = os.getenv("HOSTNAME", os.getenv("COMPUTERNAME", platform.node())).split(".")[0]

    with gr.Blocks(title=f"智慧康养模型微调中心 ({hostname})", css=CSS) as demo:
        title = gr.HTML(value=LOCALES["title"]["zh"]["value"])
        subtitle = gr.HTML(value=LOCALES["subtitle"]["zh"]["value"])
        if demo_mode:
            gr.DuplicateButton(value="Duplicate Space for private use", elem_classes="duplicate-button")

        engine.manager.add_elems("head", {"title": title, "subtitle": subtitle})
        engine.manager.add_elems("top", create_top())
        lang: gr.Dropdown = engine.manager.get_elem_by_id("top.lang")

        with gr.Tab("训练"):
            engine.manager.add_elems("train", create_train_tab(engine))

        with gr.Tab("评估预测"):
            engine.manager.add_elems("eval", create_eval_tab(engine))

        with gr.Tab("模型对话"):
            engine.manager.add_elems("infer", create_infer_tab(engine))

        if not demo_mode:
            with gr.Tab("模型导出"):
                engine.manager.add_elems("export", create_export_tab(engine))

        engine.manager.add_elems("footer", create_footer())
        demo.load(engine.resume, outputs=engine.manager.get_elem_list(), concurrency_limit=None)
        lang.change(engine.change_lang, [lang], engine.manager.get_elem_list(), queue=False)
        lang.input(save_config, inputs=[lang], queue=False)

    return demo


def create_web_demo() -> "gr.Blocks":
    engine = Engine(pure_chat=True)
    hostname = os.getenv("HOSTNAME", os.getenv("COMPUTERNAME", platform.node())).split(".")[0]

    with gr.Blocks(title=f"智慧康养模型对话演示 ({hostname})", css=CSS) as demo:
        lang = gr.Dropdown(choices=["zh", "en", "ru", "ko", "ja"], value="zh", scale=1)
        engine.manager.add_elems("top", dict(lang=lang))

        _, _, chat_elems = create_chat_box(engine, visible=True)
        engine.manager.add_elems("infer", chat_elems)

        demo.load(engine.resume, outputs=engine.manager.get_elem_list(), concurrency_limit=None)
        lang.change(engine.change_lang, [lang], engine.manager.get_elem_list(), queue=False)
        lang.input(save_config, inputs=[lang], queue=False)

    return demo


def run_web_ui() -> None:
    gradio_ipv6 = is_env_enabled("GRADIO_IPV6")
    gradio_share = is_env_enabled("GRADIO_SHARE")
    server_name = os.getenv("GRADIO_SERVER_NAME", "[::]" if gradio_ipv6 else "0.0.0.0")
    print("Visit http://ip:port for model tuning console, e.g., http://127.0.0.1:7860")
    fix_proxy(ipv6_enabled=gradio_ipv6)
    create_ui().queue().launch(share=gradio_share, server_name=server_name, inbrowser=True)


def run_web_demo() -> None:
    gradio_ipv6 = is_env_enabled("GRADIO_IPV6")
    gradio_share = is_env_enabled("GRADIO_SHARE")
    server_name = os.getenv("GRADIO_SERVER_NAME", "[::]" if gradio_ipv6 else "0.0.0.0")
    print("Visit http://ip:port for model tuning console, e.g., http://127.0.0.1:7860")
    fix_proxy(ipv6_enabled=gradio_ipv6)
    create_web_demo().queue().launch(share=gradio_share, server_name=server_name, inbrowser=True)
