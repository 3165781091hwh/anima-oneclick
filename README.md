# anima-oneclick

给 AI Agent 用的一键部署技能：说一句话，把 ComfyUI 和 Anima 模型链装好，先出一张图，再跑验收，最后交接一个能用的桌面快捷方式。

## 装好后能做什么

- 说「画一张……」就出图
- 桌面一个「Anima 生图」图标：启动、打开操作台、体检
- 出问题说「红了 / 黑了 / 慢了」，Agent 按失败码处理
- 说「有更新吗」→ 检查 ComfyUI 与前端版本；说「更新一下」→ 执行更新

## 要求

- Windows 10 / 11
- NVIDIA 显卡，显存 6GB 起（8GB 以上体验更好）
- 固定盘留 30GB 以上，首次下载约 8–10GB

## 安装这个技能

把仓库克隆到 Trae 的技能目录：

```powershell
git clone https://github.com/3165781091hwh/anima-oneclick.git "$env:USERPROFILE\.trae-cn\skills\anima-oneclick"
```

新开一个会话，对 Agent 说：

> 用 anima-oneclick 帮我把 Anima 装好，能画图就行。

安装过程只问三件事：装在哪、用哪套模型链、怎么用。默认全帮你选好。

## 里面有什么

- `SKILL.md`：Agent 的执行手册
- `references/`：安装与操作台的细节
- `presets.json` / `manifest.json` / `artists.json`：参数、素材清单、34 个画师串
- `workflows/`：API 与 WebUI 两种格式的出图流程
- `scripts/`：预检、提交出图、图片体检、更新检查
- `installer/` `console/`：安装向导与操作台

## 说明

本仓库不含模型权重，安装时按 `manifest.json` 从原始发布页下载；各模型遵循其来源页面的许可，详见 `NOTICE`。与 ComfyUI、Anima 模型作者无隶属关系。
