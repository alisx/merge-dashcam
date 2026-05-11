#!/usr/bin/env python3
"""
行车记录仪/摄像机分段视频合并工具
按文件名时间顺序，将指定范围内的视频片段合并为一个 MP4 视频。

支持格式: .ts, .mp4, .mov, .avi, .mkv, .m4v, .flv
"""

import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

__version__ = "1.1.0"

VIDEO_EXTS = {".ts", ".mp4", ".mov", ".avi", ".mkv", ".m4v", ".flv"}


def error(msg: str) -> None:
    print(f"\033[91m[错误]\033[0m {msg}", file=sys.stderr)
    sys.exit(1)


def info(msg: str) -> None:
    print(f"\033[94m[INFO]\033[0m {msg}")


def success(msg: str) -> None:
    print(f"\033[92m[OK]\033[0m {msg}")


def warn(msg: str) -> None:
    print(f"\033[93m[警告]\033[0m {msg}")


def check_ffmpeg() -> None:
    """检查 ffmpeg 是否已安装"""
    if subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0:
        if sys.platform == "win32":
            error(
                "未找到 ffmpeg。请先下载安装:\n"
                "  https://www.gyan.dev/ffmpeg/builds/ 或 https://github.com/BtbN/FFmpeg-Builds/releases\n"
                "  并将 ffmpeg.exe 所在目录添加到系统 PATH"
            )
        elif sys.platform == "darwin":
            error("未找到 ffmpeg。请先安装: brew install ffmpeg")
        else:
            error("未找到 ffmpeg。请先安装: sudo apt install ffmpeg 或 sudo pacman -S ffmpeg")


def get_video_files(directory: Path, ext: Optional[str] = None) -> list[Path]:
    """
    获取目录下所有视频文件并按文件名排序
    
    Args:
        directory: 搜索目录
        ext: 指定扩展名（如 '.ts'），None 则搜索所有支持格式
    """
    if ext:
        files = sorted(directory.glob(f"*{ext}"), key=lambda p: p.name)
    else:
        files = sorted(
            [f for f in directory.iterdir() if f.suffix.lower() in VIDEO_EXTS],
            key=lambda p: p.name,
        )
    return files


def find_file_index(files: list[Path], target: Path) -> int:
    """在排序后的文件列表中查找目标文件的索引"""
    for i, f in enumerate(files):
        if f.name == target.name:
            return i
    return -1


def format_duration(seconds: float) -> str:
    """将秒数格式化为 HH:MM:SS"""
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def probe_video_info(path: Path) -> Optional[dict]:
    """用 ffprobe 获取视频编码信息"""
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-select_streams", "v:0",
                "-show_entries", "stream=codec_name,width,height,pix_fmt,r_frame_rate",
                "-show_entries", "format=duration",
                "-of", "json",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)
    except Exception:
        return None


def get_stream_signature(info: dict) -> Optional[str]:
    """提取视频流签名，用于一致性检查"""
    try:
        stream = info["streams"][0]
        parts = [
            stream.get("codec_name", "?"),
            f"{stream.get('width', '?')}x{stream.get('height', '?')}",
            stream.get("pix_fmt", "?"),
            stream.get("r_frame_rate", "?"),
        ]
        return "|".join(parts)
    except (KeyError, IndexError):
        return None


def check_consistency(files: list[Path]) -> tuple[bool, str]:
    """
    检查所有视频文件的编码参数是否一致
    
    Returns:
        (是否一致, 信息字符串)
    """
    if not files:
        return False, "没有文件"
    
    info = probe_video_info(files[0])
    if not info:
        return False, "无法读取第一个文件的信息"
    
    first_sig = get_stream_signature(info)
    if not first_sig:
        return False, "无法提取视频签名"
    
    mismatches = []
    for f in files[1:]:
        info_i = probe_video_info(f)
        if not info_i:
            mismatches.append(f"{f.name}: 无法读取")
            continue
        sig_i = get_stream_signature(info_i)
        if sig_i != first_sig:
            mismatches.append(f"{f.name}: {sig_i}")
    
    if mismatches:
        detail = "\n  ".join([f"期望: {first_sig}"] + mismatches)
        return False, detail
    
    codec = info["streams"][0].get("codec_name", "unknown")
    res = f"{info['streams'][0].get('width', '?')}x{info['streams'][0].get('height', '?')}"
    fps = info["streams"][0].get("r_frame_rate", "?")
    return True, f"编码: {codec}, 分辨率: {res}, 帧率: {fps}"


def merge(
    start_file: Path,
    end_file: Path,
    output_file: Path,
    reencode: bool = False,
    ext: Optional[str] = None,
) -> None:
    # 确保文件存在
    if not start_file.exists():
        error(f"起始文件不存在: {start_file}")
    if not end_file.exists():
        error(f"结束文件不存在: {end_file}")

    # 确定工作目录
    directory = start_file.parent
    if end_file.parent != directory:
        error("起始文件和结束文件必须在同一目录")

    # 如果没有指定扩展名，使用起始文件的扩展名
    if ext is None:
        ext = start_file.suffix.lower()
    
    # 获取并排序所有视频文件
    all_files = get_video_files(directory, ext)
    if not all_files:
        error(f"目录中没有找到 {ext} 视频文件: {directory}")

    # 查找起始和结束索引
    start_idx = find_file_index(all_files, start_file)
    end_idx = find_file_index(all_files, end_file)

    if start_idx == -1:
        error(f"起始文件不在该目录的 {ext} 文件中: {start_file.name}")
    if end_idx == -1:
        error(f"结束文件不在该目录的 {ext} 文件中: {end_file.name}")
    if start_idx > end_idx:
        error("起始文件在结束文件之后，请检查顺序")

    # 筛选范围内的文件
    selected = all_files[start_idx : end_idx + 1]

    info(f"起始文件: {start_file.name}")
    info(f"结束文件: {end_file.name}")
    info(f"共找到 {len(selected)} 个片段待合并")

    if len(selected) == 0:
        error("没有需要合并的文件")
    elif len(selected) == 1:
        info("只有一个文件，直接复制")
        cmd = ["ffmpeg", "-y", "-i", str(selected[0]), "-c", "copy", str(output_file)]
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            error(f"ffmpeg 失败:\n{result.stderr}")
        return

    # 检查编码一致性
    if not reencode:
        consistent, detail = check_consistency(selected)
        if consistent:
            info(f"编码参数一致 ✓ ({detail})")
            info("使用无损复制模式合并（速度快、画质无损）")
        else:
            warn(f"编码参数不一致！")
            print(f"  {detail}")
            warn("这些片段无法直接无损合并。建议:")
            print("  1. 使用 --reencode 参数强制重新编码（速度慢、可能轻微损失画质）")
            print("  2. 或者确保所选片段来自同一设备同一设置")
            error("合并已取消。如需强制合并，请加上 --reencode 参数")

    # 生成 ffmpeg concat 列表文件
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as f:
        for vid_file in selected:
            # 使用绝对路径，避免工作目录问题
            # Windows 路径中的反斜杠需要处理
            abs_path = str(vid_file.resolve()).replace("\\", "/")
            f.write(f"file '{abs_path}'\n")
        list_file = f.name

    try:
        info("开始合并...")
        if reencode:
            # 重新编码模式（兼容性最好）
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c:v", "libx264",
                "-crf", "18",
                "-preset", "fast",
                "-c:a", "aac",
                "-b:a", "128k",
                "-fflags", "+genpts",
                str(output_file),
            ]
            info("重新编码模式（CRF 18，质量接近无损）...")
        else:
            # 无损复制模式
            cmd = [
                "ffmpeg",
                "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", list_file,
                "-c", "copy",
                "-fflags", "+genpts",
                str(output_file),
            ]
        
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            # 检查是否是磁盘空间问题
            if "No space left on device" in result.stderr:
                error(
                    "磁盘空间不足！\n"
                    f"  建议: 使用 -o 参数将输出保存到其他磁盘，例如:\n"
                    f"  merge-dashcam {start_file.name} {end_file.name} -o /其他磁盘/路径/output.mp4"
                )
            elif "Unsafe file name" in result.stderr:
                error(f"文件路径异常，请检查文件名是否包含特殊字符:\n{result.stderr}")
            else:
                error(f"ffmpeg 合并失败:\n{result.stderr}")
    finally:
        os.unlink(list_file)

    # 验证输出
    if not output_file.exists():
        error("输出文件未生成")

    # 获取时长
    try:
        probe = subprocess.run(
            [
                "ffprobe",
                "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(output_file),
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        duration = float(probe.stdout.strip())
    except Exception:
        duration = None

    success("合并完成!")
    print(f"  输出文件: {output_file}")
    print(f"  文件大小: {output_file.stat().st_size / (1024**3):.2f} GB")
    if duration:
        print(f"  视频时长: {format_duration(duration)}")


def auto_output_name(start_file: Path, end_file: Path) -> Path:
    """根据起始和结束文件名自动生成输出文件名"""
    start_stem = start_file.stem
    end_stem = end_file.stem

    # 去掉末尾的 F 或其他常见后缀
    start_time = re.sub(r"[Ff]$", "", start_stem)
    end_time = re.sub(r"[Ff]$", "", end_stem)

    # 如果日期相同，只保留一次
    if start_time[:8] == end_time[:8]:
        name = f"{start_time}_{end_time[9:]}_merged.mp4"
    else:
        name = f"{start_time}_{end_time}_merged.mp4"

    return Path.home() / "视频" / name


def main() -> None:
    parser = argparse.ArgumentParser(
        description="合并分段视频（支持 .ts/.mp4/.mov/.avi/.mkv 等格式）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  merge-dashcam 20260510_120726F.ts 20260510_145333F.ts
  merge-dashcam /media/dashcam/F/20260510_120726F.ts /media/dashcam/F/20260510_145333F.ts -o ~/视频/trip.mp4
  merge-dashcam clip01.mp4 clip05.mp4 --reencode
        """,
    )
    parser.add_argument("start", help="起始视频文件（含）")
    parser.add_argument("end", help="结束视频文件（含）")
    parser.add_argument(
        "-o", "--output", help="输出文件路径（默认: ~/视频/<起始>_<结束>_merged.mp4）"
    )
    parser.add_argument(
        "--reencode",
        action="store_true",
        help="强制重新编码（当片段编码参数不一致时使用，速度较慢）",
    )
    parser.add_argument(
        "--ext",
        help="指定文件扩展名过滤（如 .ts），默认使用起始文件的扩展名",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    check_ffmpeg()

    start_path = Path(args.start).expanduser().resolve()
    end_path = Path(args.end).expanduser().resolve()

    if args.output:
        output_path = Path(args.output).expanduser().resolve()
    else:
        output_path = auto_output_name(start_path, end_path)

    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)

    ext = args.ext
    if ext and not ext.startswith("."):
        ext = "." + ext

    merge(start_path, end_path, output_path, reencode=args.reencode, ext=ext)


if __name__ == "__main__":
    main()
