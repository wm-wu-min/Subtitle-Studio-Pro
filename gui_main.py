import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, colorchooser
import os
import subprocess
import threading
import json
import shutil
from PIL import Image
import sys
import datetime

# ==========================================
# 🌟 工程化路径解析 (完美适配 PyInstaller .exe 打包)
# ==========================================
if getattr(sys, 'frozen', False):
    # 如果是被打包成了 exe，以 exe 所在目录为基准
    APPLICATION_PATH = os.path.dirname(sys.executable)
else:
    # 如果是开发环境 (IDE)，以 py 脚本所在目录为基准
    APPLICATION_PATH = os.path.dirname(os.path.abspath(__file__))

# ========== 🌟 新增：全局日志强制捕获 ==========
# 打包为 --noconsole 后，拦截所有输出写入本地日志，方便查错
LOG_FILE = os.path.join(APPLICATION_PATH, "error_log.txt")


class StreamToLogger:
    def __init__(self, filename):
        self.filename = filename
        with open(self.filename, 'a', encoding='utf-8') as f:
            f.write(f"\n\n{'=' * 40}\n[程序启动] {datetime.datetime.now()}\n{'=' * 40}\n")

    def write(self, buf):
        try:
            with open(self.filename, 'a', encoding='utf-8') as f:
                f.write(buf)
        except Exception:
            pass

    def flush(self):
        pass


# 拦截所有标准输出和错误输出（仅在打包后的环境执行，不影响你在 PyCharm 里的调试）
if getattr(sys, 'frozen', False):
    sys.stdout = StreamToLogger(LOG_FILE)
    sys.stderr = sys.stdout

# 将应用程序目录加入临时系统 PATH，让代码能直接识别到同目录下的 ffmpeg.exe
os.environ["PATH"] += os.pathsep + APPLICATION_PATH

# 用户可视化文件夹
INPUT_DIR = os.path.join(APPLICATION_PATH, "input")
OUTPUT_DIR = os.path.join(APPLICATION_PATH, "output")
MODELS_DIR = os.path.join(APPLICATION_PATH, "models")  # 存放 GGUF大模型、Whisper和基础机翻模型
SETTINGS_FILE = os.path.join(APPLICATION_PATH, "config.json")

# 工作隐藏缓存区
WORKSPACE_DIR = os.path.join(APPLICATION_PATH, "workspace")
THUMB_DIR = os.path.join(WORKSPACE_DIR, "thumbnails")

for d in [INPUT_DIR, OUTPUT_DIR, MODELS_DIR, THUMB_DIR]:
    os.makedirs(d, exist_ok=True)

# ===== 核心修改：模型路径本地化 =====
# 将 HuggingFace 和 Whisper 模型的下载路径强行锁定在程序同级的 models 文件夹中
# 这样打包分享给别人时，别人就不需要重新下载模型了，完全的绿色便携版！
os.environ['HF_HOME'] = os.path.join(MODELS_DIR, "huggingface")
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
os.makedirs(os.environ['HF_HOME'], exist_ok=True)

# 强制深色模式
ctk.set_appearance_mode("Dark")

# ================= 默认配置项 =================
DEFAULT_CONFIG = {
    "llm_path": "",
    "subtitle_format": "ASS",
    "presets": ["默认风格", "Netflix 质感", "Bilibili 双语", "高亮大字"],
    "trans_styles": ["基础机翻 (快)", "自然口语 (推荐)", "诗意歌词 (感性)", "理工科专业 (严谨)"]
}


def load_config():
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                config = json.load(f)
                for k, v in DEFAULT_CONFIG.items():
                    if k not in config: config[k] = v
                return config
        except Exception:
            return DEFAULT_CONFIG
    return DEFAULT_CONFIG


def save_config(config):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


# ================= 颜色规范 =================
BG_COLOR, LIST_BG, CARD_COLOR = "#0D0D0D", "#121212", "#1A1A1A"
ACCENT_COLOR, ACCENT_HOVER = "#2196F3", "#1976D2"
STOP_COLOR, STOP_HOVER = "#FF4D4F", "#CF1322"
TEXT_MAIN, TEXT_MUTED = "#E0E0E0", "#808080"


class SettingsWindow(ctk.CTkToplevel):
    def __init__(self, master, config, update_callback):
        super().__init__(master)
        self.title("⚙️ 高级设置中心")
        self.geometry("580x650")
        self.configure(fg_color=BG_COLOR)
        self.config = config
        self.update_callback = update_callback

        self.transient(master)
        self.grab_set()

        main_frame = ctk.CTkFrame(self, fg_color=CARD_COLOR, corner_radius=12)
        main_frame.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(main_frame, text="系统与 AI 模型全局配置", font=ctk.CTkFont(size=18, weight="bold"),
                     text_color=TEXT_MAIN).pack(pady=(20, 20))

        ctk.CTkLabel(main_frame, text="本地大语言模型 (GGUF) 路径:", font=ctk.CTkFont(size=13),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(0, 5))
        llm_frame = ctk.CTkFrame(main_frame, fg_color="transparent")
        llm_frame.pack(fill="x", padx=20)
        self.entry_llm = ctk.CTkEntry(llm_frame, height=32, fg_color="#2A2A2A", border_width=1, border_color="#3E3E42")
        self.entry_llm.insert(0, self.config.get("llm_path", ""))
        self.entry_llm.pack(side="left", fill="x", expand=True, padx=(0, 10))
        ctk.CTkButton(llm_frame, text="浏览文件", width=70, height=32, fg_color="#333333", hover_color="#444444",
                      command=self.browse_llm).pack(side="right")

        ctk.CTkLabel(main_frame, text="字幕导出底层格式:", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED).pack(
            anchor="w", padx=20, pady=(20, 5))
        self.format_menu = ctk.CTkOptionMenu(main_frame, values=["ASS (高级排版)", "SRT (通用字幕)", "VTT (Web通用)",
                                                                 "LRC (音乐歌词)"],
                                             fg_color="#2A2A2A", button_color="#333333",
                                             button_hover_color=ACCENT_HOVER)
        fmt_val = self.config.get("subtitle_format", "ASS").upper()
        if "SRT" in fmt_val:
            self.format_menu.set("SRT (通用字幕)")
        elif "VTT" in fmt_val:
            self.format_menu.set("VTT (Web通用)")
        elif "LRC" in fmt_val:
            self.format_menu.set("LRC (音乐歌词)")
        else:
            self.format_menu.set("ASS (高级排版)")
        self.format_menu.pack(anchor="w", padx=20)

        ctk.CTkLabel(main_frame, text="大模型翻译风格 (用中文逗号，分隔):", font=ctk.CTkFont(size=13),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(20, 5))
        self.entry_trans = ctk.CTkEntry(main_frame, height=32, fg_color="#2A2A2A", border_width=1,
                                        border_color="#3E3E42")
        self.entry_trans.insert(0, "，".join(self.config.get("trans_styles", [])))
        self.entry_trans.pack(fill="x", padx=20)

        ctk.CTkLabel(main_frame, text="字幕排版预设 (用中文逗号，分隔):", font=ctk.CTkFont(size=13),
                     text_color=TEXT_MUTED).pack(anchor="w", padx=20, pady=(20, 5))
        self.entry_presets = ctk.CTkEntry(main_frame, height=32, fg_color="#2A2A2A", border_width=1,
                                          border_color="#3E3E42")
        self.entry_presets.insert(0, "，".join(self.config.get("presets", [])))
        self.entry_presets.pack(fill="x", padx=20)

        ctk.CTkButton(main_frame, text="✔ 保存并立即生效", font=ctk.CTkFont(size=14, weight="bold"), height=40,
                      fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, command=self.save).pack(pady=(40, 20))

    def browse_llm(self):
        # 默认从 models 目录打开
        path = filedialog.askopenfilename(title="选择 GGUF 模型文件", initialdir=MODELS_DIR,
                                          filetypes=[("GGUF Model", "*.gguf"), ("All Files", "*.*")])
        if path:
            self.entry_llm.delete(0, tk.END)
            self.entry_llm.insert(0, path)

    def save(self):
        self.config["llm_path"] = self.entry_llm.get().strip()
        fmt = self.format_menu.get()
        if "SRT" in fmt:
            self.config["subtitle_format"] = "SRT"
        elif "VTT" in fmt:
            self.config["subtitle_format"] = "VTT"
        elif "LRC" in fmt:
            self.config["subtitle_format"] = "LRC"
        else:
            self.config["subtitle_format"] = "ASS"

        trans_str = self.entry_trans.get().replace(",", "，")
        preset_str = self.entry_presets.get().replace(",", "，")
        self.config["trans_styles"] = [p.strip() for p in trans_str.split("，") if p.strip()]
        self.config["presets"] = [p.strip() for p in preset_str.split("，") if p.strip()]

        if not self.config["trans_styles"]: self.config["trans_styles"] = ["自然口语 (推荐)"]
        if not self.config["presets"]: self.config["presets"] = ["默认风格"]

        save_config(self.config)
        self.update_callback(self.config)
        self.destroy()


class VideoTaskCard(ctk.CTkFrame):
    def __init__(self, master, video_path, delete_callback, config, **kwargs):
        super().__init__(master, fg_color=CARD_COLOR, corner_radius=12, **kwargs)
        self.video_path = video_path
        self.filename = os.path.basename(video_path)
        self.delete_callback = delete_callback
        self.config = config
        self.is_completed = False

        self.model_var = ctk.StringVar(value="small (均衡)")
        self.trans_style_var = ctk.StringVar(value=self.config["trans_styles"][0])
        self.main_lang_var = ctk.StringVar(value="中文")
        self.sub_lang_var = ctk.StringVar(value="英文")

        self.supported_langs = [
            "中文", "英文", "日文", "韩文", "法文",
            "德文", "西班牙文", "俄文", "葡萄牙文", "意大利文",
            "阿拉伯文", "印地文", "泰文", "越南文", "印尼文"
        ]

        self.style_preset_var = ctk.StringVar(value=self.config["presets"][0])
        self.main_size_var = ctk.StringVar(value="22")
        self.sub_size_var = ctk.StringVar(value="14")
        self.primary_color = "#FFFFFF"
        self.outline_color = "#000000"

        self.grid_columnconfigure(1, weight=1)
        self.build_ui()
        self.load_video_info_async()

    def build_ui(self):
        self.lbl_thumb = ctk.CTkLabel(self, text="正在解析...", width=192, height=108, fg_color="#121212",
                                      text_color=TEXT_MUTED, corner_radius=8)
        self.lbl_thumb.grid(row=0, column=0, rowspan=2, padx=15, pady=15, sticky="nw")

        info_frame = ctk.CTkFrame(self, fg_color="transparent")
        info_frame.grid(row=0, column=1, padx=5, pady=(15, 0), sticky="nw")

        self.lbl_title = ctk.CTkLabel(info_frame, text=self.filename, font=ctk.CTkFont(size=18, weight="bold"),
                                      text_color=TEXT_MAIN)
        self.lbl_title.pack(anchor="w")

        self.lbl_info = ctk.CTkLabel(info_frame, text="⏳ 解析时长与大小中...", font=ctk.CTkFont(size=13),
                                     text_color=TEXT_MUTED)
        self.lbl_info.pack(anchor="w", pady=(2, 0))

        self.settings_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.settings_frame.grid(row=1, column=1, padx=5, pady=(0, 15), sticky="sw")

        main_lang_options = ["源语言"] + self.supported_langs
        sub_lang_options = ["源语言"] + self.supported_langs + ["无(单语)"]

        self._create_setting_menu(self.settings_frame, 0, 0, "听写模型", self.model_var,
                                  ["base", "small", "medium", "large-v3"], 75)
        self.menu_trans = self._create_setting_menu(self.settings_frame, 0, 1, "大模型风格", self.trans_style_var,
                                                    self.config["trans_styles"], 125)
        self._create_setting_menu(self.settings_frame, 0, 2, "主字幕", self.main_lang_var, main_lang_options, 75)
        self._create_setting_menu(self.settings_frame, 0, 3, "副字幕", self.sub_lang_var, sub_lang_options, 75)
        self.menu_preset = self._create_setting_menu(self.settings_frame, 0, 4, "预设", self.style_preset_var,
                                                     self.config["presets"], 85)
        self._create_size_config(self.settings_frame, 0, 5)
        self._create_color_config(self.settings_frame, 0, 6)

        self.progress_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.progress_bar = ctk.CTkProgressBar(self.progress_frame, height=14, corner_radius=7,
                                               progress_color=ACCENT_COLOR, fg_color="#333333")
        self.progress_bar.set(0)
        self.progress_bar.pack(side="left", fill="x", expand=True, padx=(0, 20))

        self.lbl_status = ctk.CTkLabel(self.progress_frame, text="队列等待中...",
                                       font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT_MUTED, width=130,
                                       anchor="w")
        self.lbl_status.pack(side="right")

        self.btn_delete = ctk.CTkButton(self, text="✕", width=36, height=36, corner_radius=18, fg_color="transparent",
                                        text_color=TEXT_MUTED, hover_color="#331818", font=ctk.CTkFont(size=16),
                                        command=lambda: self.delete_callback(self))
        self.btn_delete.grid(row=0, column=2, padx=15, pady=15, sticky="ne")

    def update_menus(self):
        self.menu_trans.configure(values=self.config["trans_styles"])
        self.menu_preset.configure(values=self.config["presets"])
        if self.trans_style_var.get() not in self.config["trans_styles"]: self.trans_style_var.set(
            self.config["trans_styles"][0])
        if self.style_preset_var.get() not in self.config["presets"]: self.style_preset_var.set(
            self.config["presets"][0])

    def show_progress_mode(self):
        self.settings_frame.grid_remove()
        self.btn_delete.configure(state="disabled")
        self.progress_frame.grid(row=1, column=1, padx=5, pady=(0, 15), sticky="ew")

    def show_settings_mode(self):
        if not self.is_completed:
            self.progress_frame.grid_remove()
            self.settings_frame.grid(row=1, column=1, padx=5, pady=(0, 15), sticky="sw")
            self.btn_delete.configure(state="normal")

    def update_progress(self, value, text, is_error=False, is_done=False):
        def _safe_update():
            self.progress_bar.set(value)
            self.lbl_status.configure(text=text)
            if is_error:
                self.progress_bar.configure(progress_color=STOP_COLOR)
                self.lbl_status.configure(text_color=STOP_COLOR)
            elif is_done:
                self.progress_bar.configure(progress_color="#52C41A")
                self.lbl_status.configure(text_color="#52C41A")
            else:
                self.progress_bar.configure(progress_color=ACCENT_COLOR)
                self.lbl_status.configure(text_color=ACCENT_COLOR)

        self.after(0, _safe_update)

    def _create_setting_menu(self, parent, r, c, label_text, variable, values, width):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=r, column=c, padx=(0, 8), sticky="w")
        ctk.CTkLabel(frame, text=label_text, font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w",
                                                                                                    pady=(0, 2))
        menu = ctk.CTkOptionMenu(frame, variable=variable, values=values, width=width, height=26, corner_radius=6,
                                 fg_color="#2A2A2A", button_color="#333333", button_hover_color=ACCENT_HOVER,
                                 dropdown_fg_color="#2A2A2A", dropdown_hover_color=ACCENT_HOVER,
                                 font=ctk.CTkFont(size=12))
        menu.pack(anchor="w")
        return menu

    def _create_size_config(self, parent, r, c):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=r, column=c, padx=(0, 8), sticky="w")
        ctk.CTkLabel(frame, text="字号(主/副)", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w",
                                                                                                       pady=(0, 2))
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(anchor="w")
        ctk.CTkEntry(inner, textvariable=self.main_size_var, width=32, height=26, fg_color="#2A2A2A", border_width=0,
                     justify="center").pack(side="left")
        ctk.CTkLabel(inner, text="/", text_color=TEXT_MUTED).pack(side="left", padx=2)
        ctk.CTkEntry(inner, textvariable=self.sub_size_var, width=32, height=26, fg_color="#2A2A2A", border_width=0,
                     justify="center").pack(side="left")

    def _create_color_config(self, parent, r, c):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.grid(row=r, column=c, padx=(0, 8), sticky="w")
        ctk.CTkLabel(frame, text="主色/描边", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED).pack(anchor="w",
                                                                                                     pady=(0, 2))
        inner = ctk.CTkFrame(frame, fg_color="transparent")
        inner.pack(anchor="w")
        self.btn_primary_color = ctk.CTkButton(inner, text="", width=26, height=26, corner_radius=13,
                                               fg_color=self.primary_color, hover_color=self.primary_color,
                                               border_width=2, border_color="#555",
                                               command=lambda: self.pick_color('primary'))
        self.btn_primary_color.pack(side="left")
        ctk.CTkLabel(inner, text="", width=4).pack(side="left")
        self.btn_outline_color = ctk.CTkButton(inner, text="", width=26, height=26, corner_radius=13,
                                               fg_color=self.outline_color, hover_color=self.outline_color,
                                               border_width=2, border_color="#555",
                                               command=lambda: self.pick_color('outline'))
        self.btn_outline_color.pack(side="left")

    def pick_color(self, target):
        initial = self.primary_color if target == 'primary' else self.outline_color
        color_info = colorchooser.askcolor(title="选择字幕颜色", initialcolor=initial)
        if color_info[1]:
            hex_code = color_info[1]
            if target == 'primary':
                self.primary_color = hex_code
                self.btn_primary_color.configure(fg_color=hex_code, hover_color=hex_code)
            else:
                self.outline_color = hex_code
                self.btn_outline_color.configure(fg_color=hex_code, hover_color=hex_code)

    def load_video_info_async(self):
        def task():
            try:
                size_mb = os.path.getsize(self.video_path) / (1024 * 1024)
                cmd_duration = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of',
                                'default=noprint_wrappers=1:nokey=1', self.video_path]
                duration_sec = float(subprocess.check_output(cmd_duration, text=True).strip())
                mins, secs = divmod(int(duration_sec), 60)

                thumb_path = os.path.join(THUMB_DIR, f"thumb_{abs(hash(self.video_path))}.jpg")
                is_audio = self.video_path.lower().endswith(('.mp3', '.wav', '.flac', '.m4a'))

                if not os.path.exists(thumb_path) and not is_audio:
                    cmd_cover = ['ffmpeg', '-y', '-ss', '00:00:01', '-i', self.video_path, '-frames:v', '1', '-q:v',
                                 '2', thumb_path]
                    subprocess.run(cmd_cover, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                self.after(0, self.update_ui_info, size_mb, f"{mins:02d}:{secs:02d}", thumb_path, is_audio)
            except Exception:
                self.after(0, lambda: self.lbl_info.configure(text=f"未知时长  |  {size_mb:.1f} MB"))

        threading.Thread(target=task, daemon=True).start()

    def update_ui_info(self, size_mb, duration_str, thumb_path, is_audio=False):
        self.lbl_info.configure(text=f"{duration_str}  •  {size_mb:.1f} MB")
        if os.path.exists(thumb_path):
            img = Image.open(thumb_path)
            ctk_img = ctk.CTkImage(light_image=img, dark_image=img, size=(192, 108))
            self.lbl_thumb.configure(image=ctk_img, text="")
        else:
            self.lbl_thumb.configure(text="🎵 纯音频" if is_audio else "无画面")


class ModernVideoTranslator(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.config = load_config()
        self._apply_global_env()

        self.title("Subtitle Studio Pro")
        self.geometry("1300x750")
        self.minsize(1200, 600)
        self.configure(fg_color=BG_COLOR)

        self.output_dir = ctk.StringVar(value=OUTPUT_DIR)  # 默认使用打包路径下的 output 文件夹
        self.task_cards = []
        self.is_processing = False

        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(0, weight=1)

        self.build_header()
        self.build_task_area()

        # 🌟 注册窗口关闭事件，执行清理工作
        self.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _apply_global_env(self):
        os.environ["LOCAL_GEMMA_PATH"] = self.config.get("llm_path", "")

    def build_header(self):
        header_frame = ctk.CTkFrame(self, fg_color=BG_COLOR, corner_radius=0)
        header_frame.grid(row=0, column=0, sticky="ew", padx=30, pady=(30, 10))
        header_frame.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w")
        ctk.CTkLabel(title_frame, text="Subtitle Studio", font=ctk.CTkFont(size=28, weight="bold"),
                     text_color=TEXT_MAIN).pack(side="left")
        ctk.CTkLabel(title_frame, text="Pro", font=ctk.CTkFont(size=28, weight="bold"), text_color=ACCENT_COLOR).pack(
            side="left", padx=(5, 0))

        action_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        action_frame.grid(row=0, column=1, sticky="e")

        self.btn_add = ctk.CTkButton(action_frame, text="+ 导入影音", font=ctk.CTkFont(size=14, weight="bold"),
                                     fg_color="#2A2A2A", hover_color="#333333", text_color=TEXT_MAIN,
                                     width=120, height=40, corner_radius=8, command=self.add_videos)
        self.btn_add.pack(side="left", padx=(0, 15))

        self.btn_start = ctk.CTkButton(action_frame, text="▶ 开始处理", font=ctk.CTkFont(size=14, weight="bold"),
                                       fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, text_color="#FFFFFF",
                                       width=140, height=40, corner_radius=8, command=self.toggle_processing)
        self.btn_start.pack(side="left")

        path_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        path_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(15, 0))

        ctk.CTkLabel(path_frame, text="输出目录:", font=ctk.CTkFont(size=13), text_color=TEXT_MUTED).pack(side="left")
        lbl_path = ctk.CTkLabel(path_frame, textvariable=self.output_dir, font=ctk.CTkFont(size=13),
                                text_color=TEXT_MAIN)
        lbl_path.pack(side="left", padx=(10, 10))
        ctk.CTkButton(path_frame, text="更改", width=50, height=24, fg_color="transparent", hover_color="#2A2A2A",
                      border_width=1, border_color="#333333", text_color=TEXT_MUTED,
                      command=self.choose_output_dir).pack(side="left")

        ctk.CTkButton(path_frame, text="⚙️ 系统配置", width=85, height=24, fg_color="#2A2A2A", hover_color="#333333",
                      text_color=TEXT_MAIN, command=self.open_settings).pack(side="right", padx=(10, 0))
        ctk.CTkButton(path_frame, text="清空列表", width=70, height=24, fg_color="transparent", hover_color="#331818",
                      text_color=STOP_COLOR, command=self.clear_tasks).pack(side="right")

    def build_task_area(self):
        self.list_container = ctk.CTkFrame(self, fg_color=LIST_BG, corner_radius=12, border_width=1,
                                           border_color="#1E1E1E")
        self.list_container.grid(row=1, column=0, sticky="nsew", padx=30, pady=(0, 30))
        self.list_container.grid_columnconfigure(0, weight=1)
        self.list_container.grid_rowconfigure(0, weight=1)

        self.scrollable_frame = ctk.CTkScrollableFrame(self.list_container, fg_color="transparent",
                                                       bg_color="transparent")
        self.scrollable_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)

        self.empty_label = ctk.CTkLabel(self.list_container, text="列表为空\n点击右上角「+ 导入影音」开始任务",
                                        font=ctk.CTkFont(size=16), text_color="#333333", justify="center")
        self.empty_label.place(relx=0.5, rely=0.4, anchor="center")

    def open_settings(self):
        SettingsWindow(self, self.config, self.on_config_updated)

    def on_config_updated(self, new_config):
        self.config = new_config
        self._apply_global_env()
        for card in self.task_cards:
            card.config = new_config
            card.update_menus()

    def choose_output_dir(self):
        dir_path = filedialog.askdirectory(title="选择输出目录", initialdir=OUTPUT_DIR)
        if dir_path: self.output_dir.set(dir_path)

    def add_videos(self):
        if self.is_processing: return
        # 默认从 input 文件夹中挑选文件
        files = filedialog.askopenfilenames(title="导入媒体文件", initialdir=INPUT_DIR, filetypes=[
            ("Media Files", "*.mp4 *.mkv *.mov *.avi *.mp3 *.wav *.flac *.m4a")])
        for f in files: self.add_task_card(f)

    def add_task_card(self, video_path):
        if self.empty_label.winfo_exists(): self.empty_label.place_forget()
        card = VideoTaskCard(self.scrollable_frame, video_path, delete_callback=self.remove_task, config=self.config)
        card.grid(row=len(self.task_cards), column=0, sticky="ew", padx=10, pady=(10, 5))
        self.task_cards.append(card)

    def remove_task(self, card):
        if self.is_processing: return
        card.destroy()
        self.task_cards.remove(card)
        for i, c in enumerate(self.task_cards): c.grid(row=i, column=0, sticky="ew", padx=10, pady=(10, 5))
        if not self.task_cards: self.empty_label.place(relx=0.5, rely=0.4, anchor="center")

    def clear_tasks(self):
        if self.is_processing: return
        for card in self.task_cards: card.destroy()
        self.task_cards.clear()
        self.empty_label.place(relx=0.5, rely=0.4, anchor="center")

    def toggle_processing(self):
        if not self.task_cards: return
        if not self.is_processing:
            self.is_processing = True
            self.btn_start.configure(text="■ 停止处理", fg_color=STOP_COLOR, hover_color=STOP_HOVER)
            self.btn_add.configure(state="disabled")
            for card in self.task_cards:
                if not getattr(card, 'is_completed', False):
                    card.show_progress_mode()
                    card.update_progress(0, "等待处理队列...")
            threading.Thread(target=self._process_all_tasks_thread, daemon=True).start()
        else:
            self.is_processing = False
            self.btn_start.configure(text="正在停止...", state="disabled")

    def _process_all_tasks_thread(self):
        try:
            from core.audio_extractor import AudioExtractor
            from core.speech_recognizer import SpeechRecognizer
            from core.translator import SubtitleTranslator
            from core.subtitle_generator import SubtitleGenerator
        except Exception as e:
            print(f"[严重错误] 核心模块加载失败: {e}")
            self.after(0, self._reset_ui_after_process)
            return

        output_dir = self.output_dir.get()
        os.makedirs(output_dir, exist_ok=True)
        global_translator = SubtitleTranslator()

        for card in self.task_cards:
            if not self.is_processing: break
            if card.is_completed: continue

            base_name = os.path.splitext(card.filename)[0]
            audio_path = os.path.join(WORKSPACE_DIR, f"{base_name}_temp.wav")

            ext = self.config.get("subtitle_format", "ASS").lower()
            if "srt" in ext:
                ext = "srt"
            elif "vtt" in ext:
                ext = "vtt"
            elif "lrc" in ext:
                ext = "lrc"
            else:
                ext = "ass"
            ass_path = os.path.join(output_dir, f"{base_name}.{ext}")

            try:
                model_size = card.model_var.get().split()[0]
                m_lang = card.main_lang_var.get()
                s_lang = card.sub_lang_var.get()
                trans_style = card.trans_style_var.get()

                card.update_progress(0.1, "提取无损音频中...")
                extractor = AudioExtractor()
                extractor.extract(card.video_path, audio_path)
                if not self.is_processing: break

                card.update_progress(0.4, "AI 语音听写转录中 (提取真实源语言)...")

                # 🌟 核心修改：将 Whisper 模型路径指向本地 models/whisper 文件夹
                whisper_models_dir = os.path.join(MODELS_DIR, "whisper")
                os.makedirs(whisper_models_dir, exist_ok=True)
                recognizer = SpeechRecognizer(model_size=model_size, models_dir=whisper_models_dir)

                whisper_task = "translate" if "基础机翻" in trans_style else "transcribe"
                segments = recognizer.transcribe(audio_path, task=whisper_task)
                if not self.is_processing: break

                langs_to_translate = set()
                if m_lang not in ["源语言"]: langs_to_translate.add(m_lang)
                if s_lang not in ["源语言", "无(单语)"]: langs_to_translate.add(s_lang)

                lang_results = {}
                for lang in langs_to_translate:
                    card.update_progress(0.6 + 0.1 * len(lang_results), f"Gemma 模型: 翻译至 [{lang}] 中...")
                    lang_results[lang] = global_translator.translate(segments, target_lang=lang, style=trans_style)
                    if not self.is_processing: break

                if not self.is_processing: break

                card.update_progress(0.95, f"正在渲染 {ext.upper()} 文件...")
                if not langs_to_translate:
                    base_segments = global_translator._split_long_segments(segments)
                else:
                    base_segments = list(lang_results.values())[0]

                render_segments = []
                for i in range(len(base_segments)):
                    seg = base_segments[i]
                    orig_text = seg.get('original_text', seg.get('text', ''))

                    main_t = orig_text if m_lang == "源语言" else lang_results[m_lang][i]['translated_text']

                    if s_lang == "无(单语)":
                        sub_t = ""
                    elif s_lang == "源语言":
                        sub_t = orig_text
                    else:
                        sub_t = lang_results[s_lang][i]['translated_text']

                    render_segments.append(
                        {'start': seg['start'], 'end': seg['end'], 'main_text': main_t, 'sub_text': sub_t})

                generator = SubtitleGenerator()
                if ext == "srt":
                    generator.generate_srt(render_segments, ass_path)
                elif ext == "vtt":
                    generator.generate_vtt(render_segments, ass_path)
                elif ext == "lrc":
                    generator.generate_lrc(render_segments, ass_path)
                else:
                    generator.generate_ass(render_segments, ass_path, card.main_size_var.get(), card.sub_size_var.get(),
                                           card.primary_color, card.outline_color, card.style_preset_var.get())

                card.is_completed = True
                card.update_progress(1.0, "✅ 任务完成", is_done=True)

            except Exception as e:
                card.update_progress(1.0, f"❌ 处理出错，请查看控制台", is_error=True)
                import traceback
                traceback.print_exc()
            finally:
                if os.path.exists(audio_path):
                    os.remove(audio_path)

        self.after(0, self._reset_ui_after_process)

    def _reset_ui_after_process(self):
        self.is_processing = False
        self.btn_start.configure(text="▶ 开始处理", fg_color=ACCENT_COLOR, hover_color=ACCENT_HOVER, state="normal")
        self.btn_add.configure(state="normal")
        for card in self.task_cards:
            if not card.is_completed: card.show_settings_mode()

    # 🌟 监听关闭事件：退出时清空所有的封面缓存！
    def on_closing(self):
        if os.path.exists(THUMB_DIR):
            try:
                shutil.rmtree(THUMB_DIR)
                os.makedirs(THUMB_DIR, exist_ok=True)
                print("[INFO] 退出程序，已清空封面缓存。")
            except Exception as e:
                print(f"[WARNING] 缓存清理失败: {e}")
        self.destroy()
        os._exit(0)  # 强制关闭所有残留的后台线程


if __name__ == "__main__":
    app = ModernVideoTranslator()
    app.mainloop()