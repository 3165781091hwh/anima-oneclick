# 安装向导与 P0–P6

## 开场（只说三行）

> 我先检查这台电脑，按最稳的方案装。
> 需要下载约 8–10GB，装在空间最大的那个盘，您现在可以去做别的。
> 装好我叫您。

预检不通过时不说「失败」，说三条出路：

> 这台电脑暂时不适合本地画大图，原因是大图需要更多显存。
> 三个办法：① 用云端出图；② 装「基础模型」画小图；③ 换一台有独立显卡的电脑。

## 三问（固定文案，不得改写）

```
安装选项（都可改；不想选就点“全部用推荐值”）

① 装在哪里？
   E:\AnimaAssets   剩余空间 218GB                        [更改]

② 模型与工作流
   ● A. 使用作者推荐的模型链，效果较好，出图快。
        （以 RTX 4060 为例，8–20s 一张）
   ○ B. 只安装基础模型，能满足基本生图需求，可拓展性强
        （以 RTX 4060 为例，30–60s 一张）

③ 工作方式
   ● A. 全由 Agent 托管，只需与 Agent 对话即可生图
        （token 花费量略高，适合懒人）
   ○ B. 由 Agent 生提示词，您使用可视化“简易操作台”生图
        （适合小白）
   ○ C. 由 Agent 生提示词，您使用 ComfyUI WebUI 生图
        （适合想入门 ComfyUI 的人，容易进阶）

[开始安装]   [全部用推荐值]   [恢复上次安装]

装好后也可以改：跟我说“改成基础模型”或“加回推荐链”即可，不用重装。
```

规则：向导只出现一次；「全部用推荐值」= 默认路径 + ②A + ③A 直接安装；「恢复上次安装」仅在 `state.json` 存在且未完成时出现；体积只在点「开始安装」后、下载前说一次；模型名、LoRA 名、强度、体积、分辨率一律不出现在界面上。

## plan.json

点「开始安装」时生成，落盘 `<root>\plan.json`；只放枚举，参数一律在 `presets.json`。

```json
{
  "schema": 1,
  "createdAt": "2026-10-26T21:10:00+08:00",
  "track": "portable",
  "root": "E:/AnimaAssets",
  "recipe": "quality",
  "entry": "console",
  "max_side": 1536,
  "save_dir": "E:/AnimaAssets/output",
  "phase": "full",
  "flags": {
    "install_style_loras": true,
    "register_webui_workflows": false,
    "shortcut_console": true,
    "announce_after_install": true
  },
  "steps": ["P0", "P1", "P2"],
  "last_error": null
}
```

| 字段 | 取值 | 谁读 |
|---|---|---|
| `recipe` | `quality` / `base` | 下哪些文件、查哪套参数、操作台用哪条链 |
| `entry` | `agent` / `console` / `webui` | 谁点生成、P6 告知什么、快捷方式指向哪 |
| `max_side` | `1536` / `960` / `768` | 尺寸档位上限、耗时话术 |
| `save_dir` | 路径或 `null` | 自动落盘还是单张保存 |
| `phase` | `first` / `full` / `ready` | 从哪一步续跑（`first` = P0–P2，`full` = P3 起，`ready` = P4 已过） |

四个 `flags` 由枚举派生，不引入新决策：`install_style_loras = recipe==="quality"`；`register_webui_workflows = entry==="webui"`；`shortcut_console = entry==="console"`；`announce_after_install = entry!=="agent"`。

**5 行白话摘要**（由 plan 生成，不含步数与模型名）：

1. 我先检查这台电脑，确认能跑。
2. 需要下载约 8–10GB，装在 `<root>`（未指定时写「空间最大的盘」）。
3. 装好后我先出一张图给您看。
4. 之后双击桌面「Anima 生图」就能自己画（③A 改为「跟我说一句就行」，③C 改为「打开浏览器里的画图界面」）。
5. 想换画法或换盘，跟我说，不用重装。

装完页提供「保存后续操作表」（下载 plan.json）与「复制给 Agent」（写剪贴板）。

## P0–P6 执行细节

- **P0 预检**：显卡型号与显存、驱动版本、内存、固定盘剩余（≥30GB）、端口占用、旧环境残留。运行 `python scripts/preflight.py --out <root>\preflight.json`，按输出的 `tier`（ok / marginal / below）给结论，不达标即 `BLOCKED`，不进入 P1。
- **P1 环境**：按 `manifest.json` 下载 Portable 与所选链路文件（②A 六件、②B 三件），逐件校验；`sha256` 为 `null` 时按体积（±2%）与能否被加载判定，下载完成后立刻把实际 sha256 与精确字节数回填 manifest，此后一律按 sha 校验。解压到 `runtime-portable`，写 `extra_model_paths.yaml`（`base_path` 指向 `<root>/models`），启动出图服务直到 `/system_stats` 可访问。②A↔②B 只切 LoRA 开关，不重下底模。
- **P2 首图**：`python scripts/submit.py --workflow workflows/anima-quality.json`（②B 换 `anima-base.json`），768 长边，固定提示词，出 1 张。②A 必须带 3 个 LoRA（0.7 / 0.7 / 0.85）8 步 / cfg 1；②B 无 LoRA 30 步 / cfg 4。用 `scripts/review.py` 校验非纯黑 / 纯白，结果写 `result.json`。
- **P3 基线**：同一份工作流把宽高抬到 960×1536 再出 1 张。③C 额外把 `workflows/ui-quality.json` 与 `ui-base.json`（UI 格式，WebUI 可直接载入）复制到 WebUI 的用户工作流目录；载入后若有红框，按 12 节点清单重建并覆盖该文件（E06）。
- **P4 验收**：每张图跑 `python scripts/review.py --image <png> --expect-w <w> --expect-h <h>`，再逐条核对下面 7 条；任一失败即停，按失败码处理，不放行到交接。
- **P5 交接**：桌面快捷方式「Anima 生图」、三个按钮（启动 / 打开操作台或 WebUI / 体检）、一张卡片（按本节末尾「开机三件事 / 三种颜色 / 三句话」生成）；③A 不给快捷方式文案的「双击」暗示，改成「跟我说一句」。
- **P6 告知**：③A 不告知；③B「双击桌面上的『打开操作台』，或跟我说『打开操作台』」；③C「浏览器打开 `http://127.0.0.1:8188`；关掉那个窗口，出图引擎就会停」。

## 幂等与续装

- 每步先查产物 + 校验匹配，匹配即跳过；中断后从最后完成步骤继续。
- `state.json` 在点「开始安装」时立即创建（`steps` 为空），因此 P0 / P1 中断也能续。
- 恢复时若 `state.json` 有 plan 无产物，重跑该阶段；若产物在但状态没记，补记不重做。

## 收尾与卸载

- **开机三件事**（卡片）：双击「Anima 生图」→ 等浏览器自己打开 → 跟 Agent 说「画一张……」或直接在操作台写提示词。
- **三种颜色**：绿 = 能出图，直接说需求；黄 = 能开但报错，说「黄了」；红 = 打不开，说「红了」。
- **三句话**：「红了」缺东西，Agent 查；「黑了 / 糊了」太重了，Agent 降；「慢了」图太大，Agent 调。
- **卸载**：停服务与中继 → 删快捷方式、运行时目录、`state.json` → `output\` 与 `models\` 先保留并问一句再删 → 只说删了什么、留了什么，不出现路径细节。

## 更新

- 用户问「有没有新版本」：`python scripts/update.py --check`，只报后端 / 前端 / 最新版三组数字，不改文件。
- 用户要求更新：确认出图服务已关（8188 不通），再 `python scripts/update.py --apply`；返回 2 表示非 git 安装，改走官方安装器或更新包，不自行替换文件。
- 更新后必做：重启服务、重出 1 张、跟更新前同 seed 对比；异常按 E06。
