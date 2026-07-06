import pysubs2
import os


class SubtitleGenerator:
    """全面升级的字幕渲染引擎，支持 ASS, SRT, VTT, LRC 格式生成"""

    def _hex_to_color(self, hex_str):
        hex_str = hex_str.lstrip('#')
        if len(hex_str) != 6: return pysubs2.Color(255, 255, 255)
        r, g, b = tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))
        return pysubs2.Color(r, g, b)

    def generate_ass(self, segments, output_path, main_size, sub_size, primary_hex, outline_hex, preset):
        """生成支持高级视觉排版的 ASS 视频字幕"""
        subs = pysubs2.SSAFile()
        c_primary = self._hex_to_color(primary_hex)
        c_outline = self._hex_to_color(outline_hex)

        border_style, outline_w, shadow_w, margin_v, font_name = 1, 2, 1, 15, "微软雅黑"
        if preset == "Netflix 质感":
            font_name, outline_w, shadow_w, margin_v = "黑体", 0, 2, 25
        elif preset == "高亮大字":
            font_name, outline_w, shadow_w, margin_v = "黑体", 4, 0, 20

        style = pysubs2.SSAStyle(fontname=font_name, fontsize=int(main_size), primarycolor=c_primary,
                                 outlinecolor=c_outline, borderstyle=border_style, outline=outline_w,
                                 shadow=shadow_w, alignment=2, marginv=margin_v)
        subs.styles["Default"] = style

        for seg in segments:
            start_ms, end_ms = int(seg['start'] * 1000), int(seg['end'] * 1000)
            char_count = len(seg.get('main_text', '')) + len(seg.get('sub_text', ''))
            max_duration = min(1000 + char_count * 200, 8000)
            if (end_ms - start_ms) > max_duration: end_ms = start_ms + max_duration

            main_text_fmt = f"{{\\fs{main_size}}}{seg.get('main_text', '')}"
            sub_text = seg.get('sub_text', '')
            final_text = main_text_fmt + (f"\\N{{\\fs{sub_size}}}{sub_text}" if sub_text else "")
            subs.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=final_text, style="Default"))

        subs.save(output_path)
        print(f"[{__name__}] 成功生成 ASS 字幕文件: {os.path.basename(output_path)}")

    def generate_srt(self, segments, output_path):
        """生成通用纯文本 SRT 字幕"""
        subs = pysubs2.SSAFile()
        for seg in segments:
            start_ms, end_ms = int(seg['start'] * 1000), int(seg['end'] * 1000)
            text = f"{seg.get('main_text', '')}\\N{seg.get('sub_text', '')}".strip("\\N").strip().replace("\\N", "\n")
            subs.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=text))
        subs.save(output_path, format="srt")
        print(f"[{__name__}] 成功生成 SRT 字幕文件: {os.path.basename(output_path)}")

    def generate_vtt(self, segments, output_path):
        """生成 Web 通用 VTT 字幕"""
        subs = pysubs2.SSAFile()
        for seg in segments:
            start_ms, end_ms = int(seg['start'] * 1000), int(seg['end'] * 1000)
            text = f"{seg.get('main_text', '')}\\N{seg.get('sub_text', '')}".strip("\\N").strip().replace("\\N", "\n")
            subs.append(pysubs2.SSAEvent(start=start_ms, end=end_ms, text=text))
        subs.save(output_path, format="vtt")
        print(f"[{__name__}] 成功生成 VTT 字幕文件: {os.path.basename(output_path)}")

    def generate_lrc(self, segments, output_path):
        """🌟 新增：生成各大音乐播放器通用的动感 LRC 歌词文件"""
        with open(output_path, 'w', encoding='utf-8') as f:
            for seg in segments:
                # 歌词时间轴格式: [mm:ss.xx]
                start_mins = int(seg['start'] // 60)
                start_secs = seg['start'] % 60
                timestamp = f"[{start_mins:02d}:{start_secs:05.2f}]"

                main_t = seg.get('main_text', '').strip()
                sub_t = seg.get('sub_text', '').strip()

                # 双语歌词，在同一时间点输出两行，播放器会自动显示双语
                if main_t: f.write(f"{timestamp}{main_t}\n")
                if sub_t: f.write(f"{timestamp}{sub_t}\n")

        print(f"[{__name__}] 成功生成 LRC 歌词文件: {os.path.basename(output_path)}")