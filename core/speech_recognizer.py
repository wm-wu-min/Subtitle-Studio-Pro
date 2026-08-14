import whisper
import torch
import os


class SpeechRecognizer:
    """基于 OpenAI Whisper 的高精度语音识别引擎"""

    def __init__(self, model_size="small", models_dir="models/whisper"):
        self.model_size = model_size
        self.models_dir = models_dir
        # 自动检测使用 GPU 还是 CPU
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[{__name__}] 推理设备: {self.device}")
        print(f"[{__name__}] 正在加载 Whisper 模型 ({self.model_size})...")

        # 加载模型并指定模型权重的存放路径
        self.model = whisper.load_model(self.model_size, device=self.device, download_root=self.models_dir)

    def transcribe(self, audio_path, task="transcribe", initial_prompt=""):
        """
        对音频文件进行转录，支持外部词汇表注入
        task: 'transcribe' (保持原语言) 或 'translate' (直接翻译为英语)
        initial_prompt: 注入专有名词/易错词，引导 Whisper 纠正同音词错误
        """
        print(f"[{__name__}] 开始进行语音识别，已开启词级时间戳以保证极高精度对齐...")

        # FP16 仅在 GPU 环境下支持
        use_fp16 = torch.cuda.is_available()

        # 动态组装给 whisper.transcribe 的参数字典
        transcribe_kwargs = {
            "fp16": use_fp16,
            "task": task,
            "word_timestamps": True,
            "condition_on_previous_text": False
        }

        # 🌟 核心功能：注入专业词汇表 (Glossary Prompting)
        if initial_prompt and initial_prompt.strip():
            print(f"[{__name__}] 已注入 Whisper 专有名词引导词: {initial_prompt.strip()}")
            transcribe_kwargs["initial_prompt"] = initial_prompt.strip()

        # 调用底层模型进行转录
        result = self.model.transcribe(audio_path, **transcribe_kwargs)

        # 提取包含精确时间戳的片段列表
        segments = result['segments']
        print(f"[{__name__}] 识别完成，共提取到 {len(segments)} 个字幕片段。")
        return segments