import os
import subprocess


class AudioExtractor:
    """负责从视频文件中提取音频并转换为模型适配的格式"""

    def __init__(self):
        self._check_ffmpeg()

    def _check_ffmpeg(self):
        try:
            subprocess.run(['ffmpeg', '-version'], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            print("[INFO] FFmpeg 检测成功。")
        except FileNotFoundError:
            raise EnvironmentError("未找到 FFmpeg。请确保已安装 FFmpeg 并添加到环境变量。")

    def extract(self, video_path, output_audio_path):
        """
        提取 16kHz 的单声道 WAV 音频
        """
        print(f"[{__name__}] 正在从 {video_path} 提取音频...")

        if os.path.exists(output_audio_path):
            os.remove(output_audio_path)

        command = [
            'ffmpeg',
            '-i', video_path,
            '-vn',  # 禁用视频
            '-acodec', 'pcm_s16le',  # 16位 PCM 编码
            '-ar', '16000',  # 采样率 16kHz
            '-ac', '1',  # 单声道
            output_audio_path,
            '-y'  # 覆盖输出文件
        ]

        try:
            # hide output to keep console clean
            subprocess.run(command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            print(f"[{__name__}] 音频提取完成: {output_audio_path}")
            return output_audio_path
        except subprocess.CalledProcessError as e:
            print(f"[ERROR] FFmpeg 提取失败。")
            raise