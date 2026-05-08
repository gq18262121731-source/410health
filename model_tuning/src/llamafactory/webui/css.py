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

CSS = r"""
:root {
  --health-bg: #eef7fb;
  --health-panel: rgba(255, 255, 255, 0.94);
  --health-panel-strong: #ffffff;
  --health-panel-soft: #f2fbff;
  --health-line: rgba(37, 99, 235, 0.14);
  --health-line-strong: rgba(14, 165, 233, 0.28);
  --health-text: #0f172a;
  --health-sub: #475569;
  --health-muted: #94a3b8;
  --health-brand: #2563eb;
  --health-brand-2: #06b6d4;
  --health-brand-3: #14b8a6;
  --health-ok: #10b981;
  --health-warn: #f59e0b;
  --health-danger: #ef4444;
  --health-radius-lg: 18px;
  --health-radius-md: 12px;
  --health-shadow: 0 14px 38px rgba(15, 23, 42, 0.08), 0 8px 22px rgba(6, 182, 212, 0.06);
}

html,
body,
.gradio-container {
  background:
    linear-gradient(135deg, rgba(37, 99, 235, 0.08) 0%, rgba(6, 182, 212, 0.10) 38%, rgba(16, 185, 129, 0.08) 100%),
    linear-gradient(90deg, rgba(37, 99, 235, 0.055) 1px, transparent 1px),
    linear-gradient(180deg, rgba(20, 184, 166, 0.05) 1px, transparent 1px),
    var(--health-bg) !important;
  background-size: auto, 42px 42px, 42px 42px, auto !important;
  color: var(--health-text) !important;
  font-family: "Inter", "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif !important;
}

.gradio-container {
  max-width: none !important;
  padding: 0 0 24px !important;
}

.gradio-container main.app,
.gradio-container main.fillable {
  width: 100% !important;
  max-width: none !important;
  margin: 0 !important;
  padding: 0 22px 24px !important;
}

.gradio-container > .main,
.gradio-container .wrap,
.gradio-container .contain,
.gradio-container .column {
  width: 100% !important;
  max-width: none !important;
}

.health-branding {
  display: grid;
  gap: 6px;
  margin: 0 0 12px;
  padding: 18px 22px;
  border: 1px solid rgba(125, 211, 252, 0.28);
  border-radius: 20px;
  background:
    linear-gradient(135deg, rgba(15, 23, 42, 0.96) 0%, rgba(30, 64, 175, 0.92) 52%, rgba(13, 148, 136, 0.90) 100%),
    #0f172a;
  text-align: left;
  box-shadow: 0 16px 36px rgba(15, 23, 42, 0.16), inset 0 1px 0 rgba(255, 255, 255, 0.16);
  position: relative;
  overflow: hidden;
}

.health-branding::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background:
    linear-gradient(90deg, rgba(255, 255, 255, 0.08) 1px, transparent 1px),
    linear-gradient(180deg, rgba(255, 255, 255, 0.06) 1px, transparent 1px);
  background-size: 34px 34px;
  mask-image: linear-gradient(90deg, rgba(0, 0, 0, 0.75), transparent 74%);
}

.health-branding::after {
  content: "";
  position: absolute;
  right: 26px;
  top: 18px;
  width: 88px;
  height: 88px;
  border: 1px solid rgba(125, 211, 252, 0.36);
  border-radius: 999px;
  background: radial-gradient(circle, rgba(45, 212, 191, 0.26) 0%, rgba(45, 212, 191, 0) 62%);
}

.health-branding__eyebrow {
  position: relative;
  margin: 0;
  color: #7dd3fc !important;
  font-size: 12px !important;
  font-weight: 800 !important;
  letter-spacing: 0.08em !important;
  text-transform: uppercase;
}

.health-branding h1 {
  position: relative;
  margin: 0 !important;
  color: #ffffff !important;
  font-size: clamp(22px, 2.4vw, 30px) !important;
  line-height: 1.18 !important;
  font-weight: 850 !important;
  letter-spacing: 0 !important;
}

.health-branding p {
  position: relative;
  margin: 0 !important;
  color: rgba(226, 232, 240, 0.86) !important;
  font-size: 14px !important;
  line-height: 1.7 !important;
}

.health-branding-links {
  display: none !important;
}

.gradio-container .block:has(.health-branding-links) {
  display: none !important;
}

.gradio-container .tabs {
  margin: 0 0 14px !important;
  padding: 0 !important;
  border: 0 !important;
  background: transparent !important;
}

.gradio-container .tab-nav {
  position: sticky;
  top: 0;
  z-index: 30;
  display: flex !important;
  gap: 4px !important;
  padding: 0 22px !important;
  border-bottom: 1px solid rgba(37, 99, 235, 0.16) !important;
  background: rgba(239, 247, 251, 0.88) !important;
  backdrop-filter: blur(14px);
}

.gradio-container .tab-nav button {
  min-height: 48px !important;
  padding: 0 18px !important;
  border: 0 !important;
  border-bottom: 3px solid transparent !important;
  border-radius: 0 !important;
  color: #475569 !important;
  background: transparent !important;
  font-size: 14px !important;
  font-weight: 800 !important;
}

.gradio-container .tab-nav button:hover {
  color: #0f766e !important;
  background: rgba(204, 251, 241, 0.58) !important;
}

.gradio-container .tab-nav button.selected,
.gradio-container .tab-nav button[aria-selected="true"] {
  color: #0f172a !important;
  border-bottom-color: var(--health-brand-3) !important;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(240, 253, 250, 0.96) 100%) !important;
}

.gradio-container .tabitem {
  padding: 0 22px !important;
  border: 0 !important;
  background: transparent !important;
}

.gradio-container .form,
.gradio-container .block {
  border-color: var(--health-line) !important;
  border-radius: var(--health-radius-lg) !important;
  background: var(--health-panel) !important;
  box-shadow: var(--health-shadow) !important;
  backdrop-filter: blur(16px);
}

.gradio-container .form {
  padding: 16px !important;
  overflow-x: visible !important;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.96) 0%, rgba(248, 253, 255, 0.92) 100%) !important;
}

.gradio-container .block {
  overflow: visible !important;
}

.gradio-container .gap,
.gradio-container .form > .gap,
.gradio-container .tabitem > .gap {
  gap: 14px !important;
}

.gradio-container .form .form,
.gradio-container .block .block {
  border-radius: 14px !important;
  box-shadow: none !important;
}

.gradio-container .block.padded,
.gradio-container .block.padded.auto-margin {
  min-height: 118px !important;
  min-width: 230px !important;
  padding: 16px 18px !important;
  overflow: visible !important;
  border-color: rgba(37, 99, 235, 0.16) !important;
  background:
    linear-gradient(135deg, rgba(255, 255, 255, 0.98) 0%, rgba(241, 250, 255, 0.94) 100%) !important;
  box-shadow: 0 6px 18px rgba(15, 23, 42, 0.045), inset 0 1px 0 rgba(255, 255, 255, 0.95) !important;
}

.gradio-container .block.padded label,
.gradio-container .block.padded .container {
  padding-inline: 0 !important;
}

.gradio-container label,
.gradio-container .label-wrap span,
.gradio-container .input-container label span {
  color: #334155 !important;
  font-size: 13px !important;
  font-weight: 750 !important;
}

.gradio-container .info {
  color: var(--health-muted) !important;
  font-size: 12px !important;
  line-height: 1.45 !important;
}

.gradio-container input,
.gradio-container textarea,
.gradio-container select {
  min-height: 40px !important;
  padding-inline: 14px !important;
  border: 1px solid rgba(37, 99, 235, 0.18) !important;
  border-radius: var(--health-radius-md) !important;
  background: rgba(255, 255, 255, 0.96) !important;
  color: var(--health-text) !important;
  box-shadow: inset 0 1px 2px rgba(15, 23, 42, 0.03), 0 1px 0 rgba(255, 255, 255, 0.82) !important;
}

.gradio-container input:focus,
.gradio-container textarea:focus,
.gradio-container select:focus {
  border-color: var(--health-brand-2) !important;
  box-shadow: 0 0 0 3px rgba(6, 182, 212, 0.16), 0 4px 14px rgba(6, 182, 212, 0.08) !important;
}

.gradio-container button {
  min-height: 42px !important;
  border-radius: 12px !important;
  font-weight: 800 !important;
  transition: transform 160ms ease, box-shadow 160ms ease, border-color 160ms ease, background 160ms ease !important;
}

.gradio-container button:hover {
  transform: translateY(-1px);
}

.gradio-container button.primary,
.gradio-container button[variant="primary"] {
  border: 0 !important;
  background: linear-gradient(135deg, var(--health-brand) 0%, #0891b2 55%, var(--health-brand-3) 100%) !important;
  color: #ffffff !important;
  box-shadow: 0 8px 20px rgba(6, 182, 212, 0.28), 0 2px 8px rgba(37, 99, 235, 0.18) !important;
}

.gradio-container button.stop,
.gradio-container button[variant="stop"] {
  border: 0 !important;
  background: linear-gradient(135deg, #f87171 0%, var(--health-danger) 100%) !important;
  color: #ffffff !important;
  box-shadow: 0 6px 16px rgba(239, 68, 68, 0.22) !important;
}

.gradio-container button.secondary,
.gradio-container button:not(.primary):not(.stop) {
  border: 1px solid rgba(14, 165, 233, 0.24) !important;
  background: linear-gradient(180deg, rgba(255, 255, 255, 0.98) 0%, rgba(240, 253, 250, 0.94) 100%) !important;
  color: #0f172a !important;
}

.gradio-container .accordion {
  border: 1px solid rgba(37, 99, 235, 0.14) !important;
  border-radius: 16px !important;
  background: rgba(255, 255, 255, 0.9) !important;
  box-shadow: 0 8px 22px rgba(15, 23, 42, 0.045), inset 0 1px 0 rgba(255, 255, 255, 0.86) !important;
}

.gradio-container .accordion > .label-wrap,
.gradio-container .label-wrap.svelte-1w6vloh {
  min-height: 48px !important;
  padding: 0 18px !important;
  color: #0f172a !important;
  font-weight: 800 !important;
  background: linear-gradient(135deg, rgba(239, 246, 255, 0.98) 0%, rgba(236, 253, 245, 0.92) 100%) !important;
  border: 1px solid rgba(14, 165, 233, 0.24) !important;
  border-radius: 14px !important;
  align-items: center !important;
}

.gradio-container .label-wrap.svelte-1w6vloh span,
.gradio-container .label-wrap.svelte-1w6vloh p {
  line-height: 1.4 !important;
  margin: 0 !important;
}

.gradio-container .wrap.svelte-1kajgn1 {
  min-height: 154px !important;
  min-width: 230px !important;
  display: grid !important;
  align-content: start !important;
  gap: 12px !important;
}

.gradio-container .wrap.svelte-1kajgn1 .tab-like-container {
  display: grid !important;
  grid-template-columns: 96px 38px !important;
  gap: 8px !important;
  align-items: center !important;
  justify-content: end !important;
  width: 150px !important;
  height: 42px !important;
  min-height: 42px !important;
  overflow: visible !important;
}

.gradio-container .wrap.svelte-1kajgn1 input[type="number"] {
  width: 96px !important;
  min-width: 96px !important;
  height: 40px !important;
  min-height: 40px !important;
  padding: 0 12px !important;
  text-align: center !important;
}

.gradio-container .wrap.svelte-1kajgn1 button {
  min-width: 38px !important;
  width: 38px !important;
  height: 40px !important;
  min-height: 40px !important;
  padding: 0 !important;
}

.gradio-container .slider_input_container {
  width: 100% !important;
  min-height: 42px !important;
  display: grid !important;
  grid-template-columns: 14px minmax(160px, 1fr) 56px !important;
  gap: 12px !important;
  align-items: center !important;
}

.gradio-container .slider_input_container input[type="range"] {
  width: 100% !important;
  min-width: 160px !important;
  height: 28px !important;
  padding-inline: 0 !important;
  accent-color: var(--health-brand-3) !important;
}

.gradio-container .slider_input_container span {
  color: #64748b !important;
  font-size: 12px !important;
  line-height: 1 !important;
}

.gradio-container .slider_input_container input {
  min-height: 28px !important;
}

.gradio-container label.svelte-14vb072 {
  min-height: 44px !important;
  display: inline-flex !important;
  align-items: center !important;
  gap: 10px !important;
  padding: 8px 0 !important;
  line-height: 1.45 !important;
}

.gradio-container label.svelte-14vb072 > span,
.gradio-container label.svelte-14vb072 p {
  margin: 0 !important;
  line-height: 1.45 !important;
}

.gradio-container input[type="checkbox"] {
  width: 18px !important;
  height: 18px !important;
  min-height: 18px !important;
  padding: 0 !important;
  flex: 0 0 auto !important;
  accent-color: var(--health-brand-3) !important;
}

.gradio-container .plot,
.gradio-container .plot-container,
.gradio-container [class*="plot"],
.gradio-container [class*="chart"] {
  min-height: 260px !important;
  border-color: rgba(14, 165, 233, 0.18) !important;
  background:
    linear-gradient(135deg, rgba(248, 250, 252, 0.92) 0%, rgba(240, 253, 250, 0.82) 100%) !important;
}

.gradio-container .plot:empty::after,
.gradio-container .plot-container:empty::after {
  content: "训练开始后将在这里显示损失曲线";
  display: grid;
  place-items: center;
  min-height: 240px;
  color: #64748b;
  font-size: 13px;
}

.gradio-container .wrap .wrap {
  min-width: 0 !important;
}

.gradio-container footer {
  display: none !important;
}

.duplicate-button {
  margin: auto !important;
  color: white !important;
  background: black !important;
  border-radius: 100vh !important;
}

.thinking-summary {
  padding: 8px !important;
}

.thinking-summary span {
  border-radius: 4px !important;
  padding: 4px !important;
  cursor: pointer !important;
  font-size: 14px !important;
  background: rgb(245, 245, 245) !important;
}

.dark .thinking-summary span {
  background: rgb(73, 73, 73) !important;
}

.thinking-container {
  border-left: 2px solid #a6a6a6 !important;
  padding-left: 10px !important;
  margin: 4px 0 !important;
}

.thinking-container p {
  color: #a6a6a6 !important;
}

.modal-box {
  position: fixed !important;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  max-width: 1000px;
  max-height: 750px;
  overflow-y: auto;
  background-color: var(--input-background-fill);
  flex-wrap: nowrap !important;
  border: 2px solid black !important;
  z-index: 1000;
  padding: 10px;
}

.dark .modal-box {
  border: 2px solid white !important;
}
"""
