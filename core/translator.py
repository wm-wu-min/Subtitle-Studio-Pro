import os
import re
import sys
from collections import Counter
from transformers import pipeline
import torch

try:
    from llama_cpp import Llama
except ImportError:
    print("[警告] 未安装 llama-cpp-python，大模型翻译将不可用。请运行 pip install llama-cpp-python")

# ==========================================
# 模块级全局变量 (单例缓存)
# ==========================================
_BASIC_MODEL = None
_LLM_MODEL = None

# 智能路径解析
if getattr(sys, 'frozen', False):
    PROJECT_ROOT = os.path.dirname(sys.executable)
else:
    PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_default_gemma_path = os.path.join(PROJECT_ROOT, "models", "Gemma4-e4b", "gemma-4-E4B-it-Q4_K_M.gguf")

LOCAL_GEMMA_PATH = os.environ.get("LOCAL_GEMMA_PATH", "").strip()
if not LOCAL_GEMMA_PATH:
    LOCAL_GEMMA_PATH = _default_gemma_path


class SubtitleTranslator:
    """基于本地 GGUF 模型的智能翻译引擎，支持人设切换与智能防翻车拦截"""

    def __init__(self, *args, **kwargs):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def _is_noise_segment(self, text):
        """🌟 极其强悍的噪音/环境音与幻觉拦截器"""
        # 1. 纯音乐/噪音标记拦截
        clean_text = re.sub(r'[^\w\u4e00-\u9fa5]', '', text).lower()
        noise_tags = ['', 'music', 'song', 'audio', '音乐', '歌', '歌曲', '伴奏', '前奏', '间奏', '尾奏', '掌声',
                      '笑声', '叹气']
        if clean_text in noise_tags:
            return True

        # 2. 🌟 专门拦截 Whisper 常见的“元数据”幻觉 (彻底抹杀“作词：李宗盛”等)
        text_lower = text.lower()
        hallucinations = [
            r'^(作词|作曲|编曲|演唱|后期|混音|原唱|制作人|字幕|翻译)[\s:：]',
            r'订阅频道', r'观看观看', r'谢谢观看', r'未经允许', r'禁止转载', r'请提供您需要翻译'
        ]
        for pattern in hallucinations:
            if re.search(pattern, text_lower):
                return True

        return False

    def _split_long_segments(self, segments, max_len=40, min_chunk=20):
        """升级版终极智能切割算法 (引入精确词级时间戳)"""
        split_segments = []
        for seg in segments:
            text = seg['text'].strip()

            # 🚀 终极杀招：直接抹杀噪音与幻觉段落！
            if not text or self._is_noise_segment(text):
                continue

            if len(text) > max_len and re.search(r'[,.?!，。？！;；]', text):
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

    # 🌟 修改点：接收 enable_context 参数开启全局语境纠错
    def translate(self, segments, target_lang="中文", style="自然口语 (推荐)", custom_prompt="", enable_context=False):
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

            guardrail = "【强制约束】：绝不允许自己编造“作词”、“作曲”等人员信息。如果原文无法翻译，请直接输出原文本身，严禁与之对话或解释。"

            if "自定义" in style:
                system_instruction = f"{custom_prompt}\n\n[系统指令]：将用户输入的文本翻译为【{target_lang}】。只输出最终翻译，不输出拼音或多余解释。{guardrail}"
            elif "口语" in style:
                system_instruction = f"你是一个资深海外影视剧字幕组翻译。请将以下外语字幕翻译成{target_lang}，要求极其地道、口语化。请只给出翻译结果。{guardrail}"
            elif "歌词" in style or "诗意" in style:
                system_instruction = f"你是一个顶级的音乐作词人与文学翻译家。请将以下外语歌词翻译成{target_lang}。不用拘泥于字面准确性，译文必须极具画面感。请只给出翻译结果。{guardrail}"
            else:
                system_instruction = f"你是一个理工科领域的资深专家。请将以下外语字幕翻译成{target_lang}，确保专业名词准确。请只给出翻译结果。{guardrail}"

            # 🌟 核心突破：全文高频词汇提取 (Context-Aware)
            global_keywords = ""
            if enable_context:
                print(f"[{__name__}] 正在提取全文高频词汇，构建 AI 智能纠错语境...")
                all_text_str = " ".join([seg['text'] for seg in valid_segments])
                # 提取长度 >= 4 的英文专业词汇，或长度 >= 2 的中日韩词块
                eng_words = re.findall(r'\b[a-zA-Z]{4,}\b', all_text_str.lower())
                cjk_words = re.findall(r'[\u4e00-\u9fa5]{2,}', all_text_str)
                counter = Counter(eng_words + cjk_words)
                # 选取出现次数 > 1 的 Top 30 核心词
                top_words = [w for w, count in counter.most_common(40) if count > 1][:30]
                global_keywords = "，".join(top_words)

            print(f"[{__name__}] 正在使用本地 Gemma(GGUF) 模型进行高质量翻译，请稍候...")

            for i, seg in enumerate(valid_segments):
                text = seg['text'].strip()

                # 🌟 动态注入当前句子的滑动窗口前后文
                context_prompt = ""
                if enable_context:
                    # 获取当前句子的前3句和后3句
                    start_idx = max(0, i - 3)
                    end_idx = min(len(valid_segments), i + 4)
                    surrounding_texts = [valid_segments[j]['text'].strip() for j in range(start_idx, end_idx) if j != i]
                    surrounding_context = " ".join(surrounding_texts)

                    context_prompt = (f"\n\n【智能纠错语境支持】\n"
                                      f"- 本视频高频词汇(大概率为正确的专有名词): {global_keywords}\n"
                                      f"- 当前句子的前后文: {surrounding_context}\n"
                                      f"👉 注意：请综合参考上述高频词与前后文，推断并纠正当前原句中 Whisper 可能听错的发音，确保翻译连贯准确。")

                messages = [
                    {"role": "system", "content": system_instruction + context_prompt},
                    {"role": "user", "content": f"需要翻译的原句：\n{text}"}
                ]

                temp = 0.3 if ("歌词" in style or "诗意" in style or "自定义" in style) else 0.1

                response = _LLM_MODEL.create_chat_completion(messages=messages, max_tokens=128, temperature=temp)
                translated_text = response['choices'][0]['message']['content'].strip()

                # 🌟 Fallback 处理：如果模型依然犯病，强行清洗替换为原文
                if len(translated_text) > 4 and (
                        "提供" in translated_text and ("翻译" in translated_text or "歌词" in translated_text)):
                    translated_text = text

                translated_segments.append({
                    'start': seg['start'], 'end': seg['end'],
                    'original_text': text,
                    'translated_text': translated_text
                })

                if (i + 1) % 10 == 0 or (i + 1) == len(valid_segments):
                    print(f"  -> 本地 GGUF 大模型处理进度: {i + 1}/{len(valid_segments)}")

        print(f"[{__name__}] 翻译任务彻底完成。")
        return translated_segments