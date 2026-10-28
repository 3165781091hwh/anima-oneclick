---
name: anima-oneclick
description: One-click install and run of the Anima image pipeline on Windows, including Portable setup, first image, baseline, acceptance and handoff. Use when the user asks to 装好 Anima 出图环境, 部署 anima-oneclick, or needs 操作台出图 and 画师串批量. Not for general ComfyUI tutorials.
---

# Anima 一句话部署

## 底线

1. **界面零术语**：用户可见处不出现端口、CUDA、Python、节点名、模型名、LoRA、强度、步数、cfg、分辨率、报错原文；原生报错只进「复制报错信息」剪贴板。
2. **默认 0 问**：最大固定盘 + `\AnimaAssets`、②A、③A；只有路径冲突、权限、驱动过旧、硬件不达标才打断。
3. **必须真出图**：每阶段完成由产物或脚本输出证明；模拟进度、占位图、`alert` 不算完成。
4. **单一事实来源**：参数只读 `presets.json`，文件与 hash 只读 `manifest.json`，画师串只读 `artists.json`，plan 结构只读 `installer/plan.schema.json`。不得凭记忆改数字。
5. **首图按所选链路**（D20）：②A 首图即挂 3 个 LoRA（0.7 / 0.7 / 0.85，8 步 / cfg 1），②B 首图即无 LoRA（30 步 / cfg 4），均 768 长边。先出缩水版再补视为违约。

## 阶段

| 阶段 | 做什么 | 完成标志 |
|---|---|---|
| P0 预检 | 显卡 / 驱动 / 内存 / 磁盘 / 网络 / 旧环境 / 端口 | `preflight.json`；不达标转 `BLOCKED` |
| P1 环境 | 下载 Portable + 所选链路全部素材（②A 六件 / ②B 三件）、解压、写 `extra_model_paths.yaml`、启动 | 出图服务可访问 |
| P2 首图 | 按所选链路出 1 张，768 长边 | 非黑图 + `result.json` |
| P3 基线 | 同一链路抬到 960×1536；③C 另登记两份工作流 | 基线图 1 张 |
| P4 验收 | 7 条（见下） | 全部通过 |
| P5 交接 | 快捷方式、3 个按钮、卡片（内容见 `references/install-flow.md`） | 用户能独立出图 |
| P6 告知 | 只有 ③B / ③C 需要说明入口 | 用户知道怎么开 |

附带四个脚本：`scripts/preflight.py`（P0 预检）、`scripts/submit.py`（P2/P3 与日常出图，支持 `--dry-run`）、`scripts/review.py`（P4 机械体检）、`scripts/update.py`（用户问更新先 `--check`，要求更新再 `--apply`，细节见 `references/install-flow.md` 的「更新」）。下载、解压、写 yaml、启动仍按 `references/install-flow.md` 执行。`workflows/anima-*.json` 是 API 格式供提交，`workflows/ui-*.json` 是 UI 格式供 WebUI 载入。

## 默认与打断

- 默认：`track=portable`、`recipe=quality`、`entry=console`、`max_side=1536`、`save_dir=<root>/output`。
- 打断只有四种：路径被占或无权限、驱动过旧、显存 < 6GB 或无 NVIDIA 独显、磁盘 < 30GB。
- 预检三档：显存 ≥ 8GB 达标；6–8GB 告知后可继续且长边降到 768；低于 6GB 或无 N 卡即停，给三条出路（云端出图 / 基础模型小图 / 换机器），用户选「降档」才显式改 ②B + 768。

## 状态与续装

- `state.json` 字段：`version / track / root / options / workspace / installed / steps / last_error`；点「开始安装」即创建（`steps` 为空），P0 中断也能续。
- 每步先验产物存在且校验匹配，存在即跳过；重复运行不得重复下载。
- ②A ↔ ②B 只改 LoRA 开关与采样参数，不重下底模、不重装。
- `state.json` 管台账，`plan.json` 管用户选择；冲突以 plan 为准，续装只看 state 与磁盘产物。

## 失败处置

| 码 | 处置 | 用户听到 |
|---|---|---|
| E01 | 记录版本 → 给驱动页 → 暂停 → 重启后续装 | 显卡驱动要更新，我给您一个页面；更新完跟我说一声。 |
| E02 | 换源续传，<1MB/s 即换镜像 | 下载有点慢，我换一个源再试。 |
| E03 | 对照 manifest 修正目录与文件名 | 配方少了一味材料，我来补。 |
| E04 | 降长边到 768、batch=1、关多余 LoRA | 这张太重了，我把尺寸调小再出。 |
| E05 | 换端口、放行、关代理 | 请让您的 Agent 检查此问题。 |
| E06 | 回到 12 节点母版 | 配方坏了，我重建。 |
| E07 | 换用户目录 + 白名单 | 这台电脑拦了一下，我换个位置装。 |
| E08 | 换盘、清理 | 空间不够了，我换一个盘。 |
| E09 | 单张失败不中断整批，结束汇总 | 没出成。请让您的 Agent 检查此问题。 |
| E10 | 不安装，给三条出路 | 见「预检三档」 |

同一故障连续两次修复无效即切备线，不追根因。

## 验收（7 条）

基础链 1 张 · ②A 基线 1 张（3 个 LoRA）· 操作台 01 四格数据完整 · 02 勾 3 个画师串同 seed 出 3 张 · 指定保存位置生效且清除后可单张保存 · 关掉重开后还能出图 · 备份存在。另校装完页 5 行摘要与 plan 枚举一致，操作台按 plan 打开后档位与配方一致。

## 按需加载

| 场景 | 读 |
|---|---|
| 安装向导、P0–P6 细节、交接、卸载 | `references/install-flow.md` |
| 操作台、批量、保存位置、报错面板 | `references/console-flow.md` |
| 参数与参数族 | `presets.json` |
| 文件清单与 hash | `manifest.json` |
| 画师串与插入位置 | `artists.json` |
| 出图工作流 | `workflows/anima-quality.json`（②A）、`anima-base.json`（②B）、`ui-*.json`（③C） |
| plan 字段校验与派生规则 | `installer/plan.schema.json` |

设计理由、风险与待实测不随本 skill 分发；需要时向用户索取设计档，冲突时以 JSON 为准。

## 不做

- 不打包权重、不自动抓页面、不执行模型包内脚本；只收 `.safetensors`。
- 不承诺 4G / AMD / macOS，不说「保证能跑」。
- 不新建「结果 / 历史」板块，不加第二个配置向导。
