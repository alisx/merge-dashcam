# merge-dashcam

按文件名时间顺序，自动合并行车记录仪/摄像机分段视频的命令行工具。

> 支持 `.ts`、`.mp4`、`.mov`、`.avi`、`.mkv`、`.m4v`、`.flv` 等多种格式。

## 特性

- ✅ **自动排序** — 按文件名字典序自动排序，确保时间线正确
- ✅ **范围合并** — 只需指定起始和结束文件，自动找出中间所有片段
- ✅ **无损合并** — 使用 `ffmpeg -c copy` 不重新编码，保留原画质
- ✅ **编码检查** — 合并前自动检测所有片段编码参数是否一致，防止花屏
- ✅ **重新编码** — 编码不一致时可用 `--reencode` 强制合并
- ✅ **跨平台** — 支持 Windows、macOS、Linux

## 安装

### 前提条件

需要先安装 **ffmpeg** 和 **ffprobe**：

| 平台 | 安装方式 |
|------|----------|
| Windows | [下载 ffmpeg](https://www.gyan.dev/ffmpeg/builds/)，将 `bin` 目录加入系统 PATH |
| macOS | `brew install ffmpeg` |
| Ubuntu/Debian | `sudo apt install ffmpeg` |
| Arch Linux | `sudo pacman -S ffmpeg` |

### 安装本工具

```bash
pip install git+https://github.com/yourname/merge-dashcam.git
```

或从源码安装：

```bash
git clone https://github.com/yourname/merge-dashcam.git
cd merge-dashcam
pip install .
```

## 使用方法

### 基本用法

在视频所在目录执行：

```bash
merge-dashcam 20260510_120726F.ts 20260510_145333F.ts
```

输出将保存到 `~/视频/20260510_120726_145333_merged.mp4`（Linux/macOS）。

### 指定输出路径

```bash
merge-dashcam 20260510_120726F.ts 20260510_145333F.ts -o ~/桌面/行车记录.mp4
```

### 使用绝对路径

```bash
merge-dashcam /media/dashcam/F/20260510_120726F.ts /media/dashcam/F/20260510_145333F.ts
```

### 强制重新编码

当片段编码参数不一致时（比如来自不同设备）：

```bash
merge-dashcam clip01.mp4 clip05.mp4 --reencode
```

## 示例输出

```
[INFO] 起始文件: 20260510_120726F.ts
[INFO] 结束文件: 20260510_145333F.ts
[INFO] 共找到 81 个片段待合并
[INFO] 编码参数一致 ✓ (编码: h264, 分辨率: 1920x1080, 帧率: 30/1)
[INFO] 使用无损复制模式合并（速度快、画质无损）
[INFO] 开始合并...
[OK] 合并完成!
  输出文件: /home/alisx/视频/20260510_120726_145333_merged.mp4
  文件大小: 5.90 GB
  视频时长: 01:19:56
```

## 命令行参数

```
usage: merge-dashcam [-h] [-o OUTPUT] [--reencode] [--ext EXT] [-v] start end

positional arguments:
  start              起始视频文件（含）
  end                结束视频文件（含）

options:
  -h, --help         显示帮助信息
  -o, --output       输出文件路径
  --reencode         强制重新编码（编码不一致时使用）
  --ext              指定文件扩展名过滤（如 .ts）
  -v, --version      显示版本号
```

## 许可证

MIT License
