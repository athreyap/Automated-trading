import shutil
import subprocess
import tempfile
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


def run_command(command):
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout)[-4000:])
    return result.stdout


def media_duration(path):
    output = run_command([
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ])
    return max(0.1, float(output.strip()))


def render_reel(
    paths,
    output,
    target_seconds=30,
    video_clip_seconds=4,
    image_seconds=2,
    music_path=None,
):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("FFmpeg and FFprobe are required. See packages.txt.")

    sources = [
        Path(path) for path in paths
        if Path(path).suffix.lower() in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS
    ]
    if not sources:
        raise ValueError("No supported images or videos were supplied.")

    work_dir = Path(tempfile.mkdtemp(prefix="reel_render_"))
    segments = []
    used = []
    elapsed = 0.0

    for index, source in enumerate(sources):
        if elapsed >= target_seconds:
            break

        is_image = source.suffix.lower() in IMAGE_EXTENSIONS
        segment_seconds = min(
            image_seconds if is_image else video_clip_seconds,
            target_seconds - elapsed,
        )
        segment = work_dir / f"segment_{index:03d}.mp4"
        video_filter = (
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=30,format=yuv420p"
        )

        if is_image:
            command = [
                "ffmpeg", "-y", "-loop", "1", "-i", str(source),
                "-t", str(segment_seconds), "-vf", video_filter,
                "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "23", "-pix_fmt", "yuv420p", str(segment),
            ]
        else:
            source_duration = media_duration(source)
            start = max(0, (source_duration - segment_seconds) / 2)
            command = [
                "ffmpeg", "-y", "-ss", str(start), "-i", str(source),
                "-t", str(segment_seconds), "-vf", video_filter,
                "-an", "-c:v", "libx264", "-preset", "veryfast",
                "-crf", "23", "-pix_fmt", "yuv420p",
                "-movflags", "+faststart", str(segment),
            ]

        run_command(command)
        segments.append(segment)
        elapsed += segment_seconds
        used.append({
            "filename": source.name,
            "seconds": round(segment_seconds, 2),
            "kind": "photo" if is_image else "video",
        })

    if not segments:
        raise RuntimeError("No segments could be rendered.")

    concat_file = work_dir / "concat.txt"
    concat_file.write_text(
        "".join(f"file '{segment.as_posix()}'\n" for segment in segments),
        encoding="utf-8",
    )
    joined = work_dir / "joined.mp4"
    run_command([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(concat_file), "-c", "copy",
        "-movflags", "+faststart", str(joined),
    ])

    output_path = Path(output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if music_path:
        command = [
            "ffmpeg", "-y", "-i", str(joined),
            "-stream_loop", "-1", "-i", str(music_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-t", str(elapsed), "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k", "-shortest",
            "-movflags", "+faststart", str(output_path),
        ]
    else:
        command = [
            "ffmpeg", "-y", "-i", str(joined),
            "-c:v", "copy", "-an", "-movflags", "+faststart",
            str(output_path),
        ]
    run_command(command)

    return {
        "output": str(output_path),
        "duration_seconds": round(elapsed, 2),
        "resolution": "1080x1920",
        "fps": 30,
        "video_codec": "H.264",
        "audio": "music track" if music_path else "none",
        "clips_used": used,
        "editing_mode": "automatic assembly in selected order",
        "limitations": [
            "No semantic scene ranking yet",
            "Landscape footage uses a centered crop",
            "No beat detection or speech subtitles yet",
        ],
    }
