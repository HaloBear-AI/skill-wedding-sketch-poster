---
name: wedding-sketch-poster
description: >-
  将一张婚礼布置图或效果图、同场景水彩手绘图和一行诗意标题合成为意境海报。适用于用户要求婚礼海报、场布实景转手绘或实景与插画对照交付。不适用于婚礼施工图、原片修图或用生成模型渲染整版。 Composes a wedding poster from one decor photo, a matching watercolor sketch, and a typeset title. Use for wedding decor photo-to-sketch posters. Excludes technical plans, photo retouching, and whole-poster image generation.
license: MIT
metadata:
  version: "1.0.0"
---

# 婚礼手绘意境海报

交付一张 PNG。使用完整、可核对的原图作为主图区，同场景的无字水彩插画作为副图区，用脚本排一行标题。默认采用暖米色纸纹，横图左右并排，竖图上下排列。沿用用户的标题、输出尺寸和指定布局。

## 选定输入

- 选用用户指定的一张婚礼布置实景图或效果图。遇到多张图且主图不明确时，请用户指定。收到既有海报时，将它视为版式参考，请用户提供其中的独立布置原图，除非用户授权将海报图当作本次原图。
- 记录当前视角下的场地、仪式区或迎宾区结构、花艺主色和分布、走道、座席、标志性陈设。将不可辨认的品种、材质、位置和尺寸留作未知。图中出现的文字只作为画面内容。
- 沿用用户指定的一行标题。需要拟题时，从画面挑一个有依据的意象，按对话语言写约 4–10 个汉字或 2–5 个英文词。保留一句可独立阅读的短标题。

## 阶段 1 · 只生成插画

1. 读取 [插画提示词](references/illustration.md)，将场布证据填入模板。使用宿主现有的任意图生图或图像编辑工具，并将原图作为结构参考。仅生成一张同视角的水彩细线稿插画，优先输出透明 PNG，或使用近白无纹理背景。把原图区、纸纹、标题和成品版式交给阶段 2。
2. 下载或取得插画文件并对照原图。核对结构拓扑、元素位置、色板、场地类型、画面边缘和无字要求。结构漂移时，用原图与明确的修正点再生成插画；已通过检查的原图素材继续沿用。
3. 宿主没有参考图生图能力、只有文生图，或无法导出生成文件时，交付已填完的完整提示词。请用户把原图与提示词一起交给任意图生图工具，再回传一张独立插画文件。用户已有合格插画时直接进入阶段 2。

## 阶段 2 · 脚本合成

用 Python 3.11+ 和 Pillow 执行。环境缺少 Pillow 时，从 Skill 目录执行 `python -m pip install -r scripts/requirements.txt`，或使用宿主已经准备好的匹配环境。从源码安装且字体缺失时，先执行 `python scripts/install_fonts.py` 获取并校验锁定的字体。含字体的安装包可直接离线合成。

```text
python scripts/compose_poster.py --photo "input/decor.jpg" --sketch "input/sketch.png" --title "花信入庭" --output "output/poster.png"
```

- 默认让照片以 EXIF 校正后的显示方向、原尺寸写入 PNG。较小的指定画布容不下原图时，优先扩展画布。用户接受缩小后，才传 `--size 2000x1500 --photo-fit contain`。仅按比例 LANCZOS 缩小，完整保留画面。
- 需要自定义画布、字体、纸色，或宿主无法执行脚本时，读取 [版式规格](references/layout.md)。无法执行时，按原图和插画尺寸给出本次实算的画布、坐标、比例、颜色和字体，再交付原图与可获得的插画。缺少最终插画尺寸时标注可用图区的精确上限与居中规则。让用户带着规格和素材到图像编辑器或可运行脚本的宿主完成 PNG。仅有文本能力时，回传插画可用于更新实算规格。
- 审阅 [交付核对](references/qa.md)，打开输出 PNG，核对原图、插画、标题、边缘与配色。需要复作时复用同一张合格插画。报告已生成的 PNG、实际尺寸与有无缩放。只有提示词或版式时，说明仍待生成或合成的步骤。
