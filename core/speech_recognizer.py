import whisper
import torch
import os


class SpeechRecognizer:
    """负责使用 Whisper 模型进行语音识别并提取时间轴"""

    def __init__(self, model_size="small", models_dir="./models/whisper"):
        self.model_size = model_size
        self.models_dir = models_dir

        # 确保模型下载目录存在
        os.makedirs(self.models_dir, exist_ok=True)

        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[{__name__}] 推理设备: {self.device}")

        print(f"[{__name__}] 正在加载 Whisper 模型 ({self.model_size})...")
        # download_root 参数指定了模型下载和加载的本地路径
        self.model = whisper.load_model(
            self.model_size,
            device=self.device,
            download_root=self.models_dir
        )

    # 1. 这里必须加上 task="transcribe" 参数
    def transcribe(self, audio_path, task="transcribe"):
        """对音频文件进行转录
           task: 'transcribe' (保持原语言) 或 'translate' (翻译为英语)
        """
        print(f"[{__name__}] 开始进行语音识别，已开启词级时间戳(Word-level Timestamps)以保证极高精度对齐...")
        # FP16 仅在 GPU 上支持
        use_fp16 = torch.cuda.is_available()

        # 2. 🌟 关键修改：开启 word_timestamps=True 提供精确词汇切割！
        # 同时开启 condition_on_previous_text=False，解决幻觉循环和时间轴微漂移问题
        result = self.model.transcribe(
            audio_path,
            fp16=use_fp16,
            task=task,
            word_timestamps=True,
            condition_on_previous_text=False
        )

        segments = result['segments']
        print(f"[{__name__}] 识别完成，共提取到 {len(segments)} 个字幕片段。")
        return segments