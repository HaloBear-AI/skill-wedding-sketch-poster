# Wedding Sketch Poster · 婚礼手绘意境海报

从一张婚礼布置实景或效果图制作意境海报。宿主的参考图生图工具只画独立插画，离线 Python 脚本负责纸纹、原图、插画和一行标题。默认原图区以原尺寸写入无损 PNG。支持实景横排、竖图上下排和中英文标题。

## 安装

1. 将 [wedding-sketch-poster](wedding-sketch-poster) 整个目录放进宿主的 Agent Skills 目录，保留同名目录和 `SKILL.md`。
2. 准备 Python 3.11 或以上。macOS、Linux 在终端使用 `python` 或 `python3`，Windows 可用 `py -3`。在 Skill 目录执行 `python -m pip install -r scripts/requirements.txt`。
3. GitHub 源码安装时，在同一目录执行 `python scripts/install_fonts.py`。首次联网获取固定的 OFL 字体并校验 SHA-256。随附字体的 ZIP 安装包可跳过这一步。

```text
python scripts/compose_poster.py --photo "input/decor.jpg" --sketch "input/sketch.png" --title "花信入庭" --output "output/poster.png"
```

## 最小使用示例

在支持 Agent Skills 的宿主上传一张婚礼布置图并说「用 `wedding-sketch-poster` 做一张意境海报，标题是『花信入庭』。」宿主有参考图生图能力时可完成两阶段。只有文本能力时，先取得 [可直接使用的插画提示词](wedding-sketch-poster/references/illustration.md)，按需使用 [人工合成坐标与颜色规格](wedding-sketch-poster/references/layout.md)。

原图支持单帧、不透明、8 位 PNG、JPEG 或 WebP。插画接受透明 PNG 或四周留有均匀近白底的单图。脚本校正 EXIF 方向，PNG 原图区逐像素保留校正后解码的 RGB 值。有 RGB ICC 时保留图像的配色空间。`--size` 用于固定画布，`--photo-fit contain` 用于用户允许的等比缩小。`--help` 显示其余参数。相同输入和参数在相同 Python/Pillow 构建下生成相同 PNG 字节。

## Fonts and license

项目代码和说明采用 MIT。Cutive Mono Regular 和 Noto Sans SC Variable 依各字体的 SIL Open Font License 1.1 分发，授权文件位于 `wedding-sketch-poster/assets/fonts/`。[Cutive Mono 源码与授权](https://github.com/google/fonts/tree/main/ofl/cutivemono) · [Noto Sans SC 源码与授权](https://github.com/google/fonts/tree/main/ofl/notosanssc)
