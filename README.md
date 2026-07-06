# **🎬 Subtitle Studio Pro**

**Subtitle Studio Pro** 是一款极其强大的本地化 AI 视频/音频翻译与字幕生成工具。

它结合了 **Whisper (词级时间戳精切)** 与 **Gemma (本地 GGUF 大模型)**，为您提供极致的音画同步体验与饱含“人情味”的翻译质量。

完全本地运行，保护隐私，拒绝机翻味！

## **✨ 核心特性**

* 🧠 **大模型智能翻译**：原生支持本地加载 .gguf 大语言模型 (如 Gemma-4)。支持动态切换人设提示词（“自然口语”、“理工科严谨”、“诗意歌词”等）。  
* ⏱️ **词级精准切轴**：抛弃传统的等比例切轴法。开启 Whisper word\_timestamps，哪怕一长段话中被逗号切分，也能实现 100% 毫秒级音画同步。  
* 🎵 **支持纯音频与 LRC 动感歌词**：支持导入 .mp4, .mp3, .flac 等格式。可一键生成各大音乐播放器支持的 .lrc 双语滚动歌词。  
* 🎨 **多种字幕格式导出**：支持 ASS (支持 Netflix 质感、B站等自定义高级排版)、SRT (通用纯文本)、VTT (Web通用) 以及 LRC。  
* 🖥️ **现代化暗黑 GUI**：基于 CustomTkinter 打造的高级质感界面，支持进度条实时反馈与全局配置持久化。

## **🚀 安装指南**

### **1\. 基础环境**

请确保你的电脑已安装 **Python 3.10+**，并且已配置 **FFmpeg** 环境变量。

### **2\. 克隆仓库与安装依赖**

git clone \[https://github.com/你的用户名/SubtitleStudioPro.git\](https://github.com/你的用户名/SubtitleStudioPro.git)  
cd SubtitleStudioPro  
pip install \-r requirements.txt

### **3\. 安装 Llama-cpp-python (用于 GPU 加速本地大模型)**

为了发挥 NVIDIA 显卡的全部性能极速运行 GGUF 模型，请安装带有 CUDA 支持的 llama-cpp-python：

\# 示例：针对 CUDA 12.1+ 的安装命令  
pip install llama-cpp-python \--extra-index-url \[https://abetlen.github.io/llama-cpp-python/whl/cu121\](https://abetlen.github.io/llama-cpp-python/whl/cu121)

## **🛠️ 使用方法**

1. 运行主程序启动可视化界面：  
   python gui\_main.py

2. **配置大模型**：点击左下角 **“⚙️ 系统配置”**。  
   * 选择你的本地 .gguf 模型路径（推荐使用 Gemma 系列）。  
   * 选择你想要的字幕导出格式。  
3. **导入文件**：点击右上角 **“+ 导入影音”**。  
4. **选择风格**：在任务卡片中，你可以为每个视频单独选择翻译风格（如：诗意歌词）。  
5. 点击 **“▶ 开始处理”**，静享极速的本地 AI 翻译！

## **📂 项目目录结构**

如果你希望将其打包为绿色便携版(.exe)，项目运行时会自动生成以下目录结构：

SubtitleStudioPro/  
├── core/                  \# 核心识别与翻译引擎  
├── gui\_main.py            \# 主程序入口  
├── config.json            \# (自动生成) 用户配置文件  
├── input/                 \# (自动生成) 推荐将待处理媒体放于此  
├── output/                \# (自动生成) 字幕/歌词导出目录  
└── models/                \# 存放你的 GGUF 大模型

## **📜 许可证**

本项目基于 [MIT License](http://docs.google.com/LICENSE) 开源。欢迎提交 Issue 和 Pull Request！