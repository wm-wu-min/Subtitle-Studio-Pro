from transformers import pipeline
import torch
import os
import re
import sys

try:
    from llama_cpp import Llama
except ImportError:
    print("[警告] 未安装 llama-cpp-python，大模型翻译将不可用。请运行 pip install llama-cpp-python")

# ==========================================
# 模块级全局变量 (单例缓存)
# ==========================================
_BASIC_MODEL = None
_LLM_MODEL = None

# ==========================================
# ⬇️ 【修复打包路径识别：精准定位 exe 同级目录】 ⬇️
# ==========================================
if getattr(sys, 'frozen', False):
    # 如果是被打包成了 exe，以 exe 所在目录为基准
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    # 如果是源码运行，以当前 py 脚本所在目录的上两级为基准
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# 默认的 Gemma 模型相对路径
_default_gemma_path = os.path.join(PROJECT_ROOT, "models", "Gemma4-e4b", "gemma-4-E4B-it-Q4_K_M.gguf")

# 优先读取 GUI 设置里传过来的路径，如果用户没填，则强制使用上面的准确默认路径
LOCAL_GEMMA_PATH = os.environ.get("LOCAL_GEMMA_PATH", "").strip()
if not LOCAL_GEMMA_PATH:
    LOCAL_GEMMA_PATH = _default_gemma_path


class SubtitleTranslator:
    """基于本地 GGUF 模型的智能翻译引擎，支持人设切换"""

    def __init__(self, *args, **kwargs):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def _split_long_segments(self, segments, max_len=40, min_chunk=20):
        """升级版终极智能切割算法 (引入精确词级时间戳)"""
        split_segments = []
        for seg in segments:
            text = seg['text'].strip()

            if len(text) > max_len and re.search(r'[,.?!，。？！;；]', text):
                # 🚀 方案 A：精准词级时间戳切分
                if 'words' in seg and seg['words']:
                    current_text = ""
                    current_words = []
                    for word_info in seg['words']:
                        word_text = word_info['word']
                        current_text += word_text
                        current_words.append(word_info)
                        if re.search(r'[,.?!，。？！;；]', word_text) and len(current_text.strip()) >= min_chunk:
                            split_segments.append({
                                'start': current_words[0]['start'],
                                'end': current_words[-1]['end'],
                                'text': current_text.strip()
                            })
                            current_text = ""
                            current_words = []
                    if current_words:
                        if len(current_text.strip()) < min_chunk and split_segments:
                            split_segments[-1]['text'] += current_text
                            split_segments[-1]['end'] = current_words[-1]['end']
                        else:
                            split_segments.append({
                                'start': current_words[0]['start'],
                                'end': current_words[-1]['end'],
                                'text': current_text.strip()
                            })
                    continue

                    # 🚀 方案 B：(降级防错) 按字数比例估算
                parts = re.split(r'([,.?!，。？！;；])', text)
                raw_sub_texts = []
                temp_str = ""
                for part in parts:
                    temp_str += part
                    if part in ",.?!，。？！;；":
                        if temp_str.strip(): raw_sub_texts.append(temp_str.strip())
                        temp_str = ""
                if temp_str.strip(): raw_sub_texts.append(temp_str.strip())

                merged_sub_texts = []
                current_chunk = ""
                for sub in raw_sub_texts:
                    if not current_chunk:
                        current_chunk = sub
                    elif len(current_chunk) < min_chunk:
                        if current_chunk[-1].encode('UTF-8').isalpha():
                            current_chunk += " " + sub
                        else:
                            current_chunk += sub
                    else:
                        merged_sub_texts.append(current_chunk.strip())
                        current_chunk = sub
                if current_chunk: merged_sub_texts.append(current_chunk.strip())

                if len(merged_sub_texts) > 1:
                    total_chars = sum(len(s) for s in merged_sub_texts)
                    total_duration = seg['end'] - seg['start']
                    curr_start = seg['start']
                    for s_text in merged_sub_texts:
                        ratio = len(s_text) / total_chars if total_chars > 0 else 0
                        duration = total_duration * ratio
                        curr_end = curr_start + duration
                        split_segments.append({'start': curr_start, 'end': curr_end, 'text': s_text})
                        curr_start = curr_end
                    continue
            split_segments.append(seg)
        return split_segments

    def translate(self, segments, target_lang="中文", style="自然口语 (推荐)"):
        global _BASIC_MODEL, _LLM_MODEL
        print(f"[{__name__}] 启动翻译引擎 | 目标: {target_lang} | 风格: {style}")

        valid_segments = [seg for seg in segments if seg['text'].strip()]
        if not valid_segments: return []

        print(f"[{__name__}] 正在进行字幕切轴预处理 (打碎长段落，利用精确词级时间戳)...")
        valid_segments = self._split_long_segments(valid_segments)

        translated_segments = []

        if "基础机翻" in style:
            if _BASIC_MODEL is None:
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    _BASIC_MODEL = pipeline("translation", model="Helsinki-NLP/opus-mt-en-zh",
                                            device=0 if self.device == "cuda" else -1)

            texts = [seg['text'].strip() for seg in valid_segments]
            results = _BASIC_MODEL(texts, batch_size=16)

            for i, seg in enumerate(valid_segments):
                translated_segments.append({
                    'start': seg['start'], 'end': seg['end'],
                    'original_text': seg['text'].strip(),
                    'translated_text': results[i]['translation_text']
                })
        else:
            if _LLM_MODEL is None:
                if not os.path.exists(LOCAL_GEMMA_PATH):
                    raise FileNotFoundError(f"找不到模型文件: {LOCAL_GEMMA_PATH}\n请检查路径是否正确！")
                _LLM_MODEL = Llama(
                    model_path=LOCAL_GEMMA_PATH,
                    n_gpu_layers=-1,
                    n_ctx=2048,
                    verbose=False
                )

            # --- 🌟 核心：新增音乐歌词专属作词人人设 ---
            if "口语" in style:
                system_instruction = f"你是一个资深海外影视剧字幕组翻译。请将以下外语字幕翻译成{target_lang}，要求极其地道、口语化，符合日常交流的语气，坚决避免机器翻译的生硬感。请只给出最终的翻译结果，不要输出任何多余的解释、标点、拼音或前缀语句。"
            elif "歌词" in style or "诗意" in style:
                system_instruction = f"你是一个顶级的音乐作词人与文学翻译家。请将以下外语歌词翻译成{target_lang}。要求：充分体会歌曲的情感与意境，不用拘泥于字面准确性，译文必须极具画面感、充满诗意且符合歌词的韵律美。请只给出最终的歌词翻译结果，绝对不要输出任何多余的解释、分析或拼音。"
            else:
                system_instruction = f"你是一个理工科（计算机、物理、数学、电子等）领域的资深博士与专业翻译。请将以下外语字幕翻译成{target_lang}，必须确保所有专业名词极其准确严谨。请只给出最终的翻译结果，不要输出任何多余的解释、拼音或前缀语句。"

            print(f"[{__name__}] 正在使用本地 Gemma(GGUF) 模型进行高质量翻译，请稍候...")

            for i, seg in enumerate(valid_segments):
                text = seg['text'].strip()
                messages = [
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": f"需要翻译的原句：\n{text}"}
                ]

                # 歌词需要更多的发散性，适当调高 temperature (0.3)
                temp = 0.3 if ("歌词" in style or "诗意" in style) else 0.1

                response = _LLM_MODEL.create_chat_completion(messages=messages, max_tokens=128, temperature=temp)
                translated_text = response['choices'][0]['message']['content'].strip()

                translated_segments.append({
                    'start': seg['start'], 'end': seg['end'],
                    'original_text': text,
                    'translated_text': translated_text
                })

                if (i + 1) % 10 == 0 or (i + 1) == len(valid_segments):
                    print(f"  -> 本地 GGUF 大模型处理进度: {i + 1}/{len(valid_segments)}")

        print(f"[{__name__}] 翻译任务彻底完成。")
        return translated_segments