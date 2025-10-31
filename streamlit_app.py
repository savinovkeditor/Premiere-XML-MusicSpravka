import streamlit as st
import pandas as pd
import xml.etree.ElementTree as ET
from collections import OrderedDict
import re
from io import StringIO

# === Автор: Савинов Кирилл ===
# Для связи: savinov.k.editor@gmail.com

# --- Твоя логика парсинга (адаптирована под загрузку файла в память) ---
def parse_track_name(filename):
    name = filename.rsplit('.', 1)[0]
    parts = name.split('_')
    for i in range(len(parts)-1, -1, -1):
        if '-' in parts[i]:
            author_raw = parts[i]
            track_parts = parts[:i]
            break
    else:
        author_raw = ''
        track_parts = parts

    prefix_match = re.match(r'^([a-zA-Z]+_[a-zA-Z0-9]+_[0-9_]+_)', name)
    prefix = prefix_match.group(1) if prefix_match else '_'.join(parts[:3]) + '_'

    track_core = name[len(prefix):].rsplit('_', 1)[0] if prefix else track_parts[-1]
    track_core = track_core.replace('-', ' ').replace('_', ' ').strip().title()
    author_name = author_raw.replace('-', ' ').replace('_', ' ').strip().title() if author_raw else ''

    return prefix, track_core, author_name


def seconds_to_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{int(h):02}:{int(m):02}:{int(s):02}"


def parse_premiere_xml(file, fps=25):
    tree = ET.parse(file)
    root = tree.getroot()

    tracks_data = OrderedDict()
    seen_linked = set()

    for clip in root.iter("clipitem"):
        link_refs = [l.text.strip() for l in clip.findall("link/linkclipref") if l.text]
        if any(ref in seen_linked for ref in link_refs):
            continue
        for ref in link_refs:
            seen_linked.add(ref)
        seen_linked.add(clip.attrib.get("id", ""))

        file_elem = clip.find("file")
        filename = None
        if file_elem is not None:
            name_elem = file_elem.find("name")
            if name_elem is not None and name_elem.text:
                filename = name_elem.text.strip()
        if not filename:
            name_elem = clip.find("name")
            if name_elem is not None and name_elem.text:
                filename = name_elem.text.strip()
        if not filename:
            continue

        prefix, track_name, author_name = parse_track_name(filename)

        in_elem = clip.find("in")
        out_elem = clip.find("out")
        if in_elem is None or out_elem is None:
            continue
        try:
            in_frame = int(in_elem.text.strip())
            out_frame = int(out_elem.text.strip())
        except Exception:
            continue
        if out_frame <= in_frame:
            continue

        duration_frames = out_frame - in_frame
        key = (prefix, track_name)
        if key in tracks_data:
            tracks_data[key]['frames'] += duration_frames
            tracks_data[key]['count'] += 1
        else:
            tracks_data[key] = {
                'frames': duration_frames,
                'author': author_name,
                'count': 1
            }

    result = []
    for (prefix, track), d in tracks_data.items():
        total_seconds = round(d['frames'] / fps)
        result.append({
            'Prefix': prefix,
            'Track': track,
            'Author': d['author'],
            'Repeats': d['count'],
            'Duration (HH:MM:SS)': seconds_to_hms(total_seconds),
            'Seconds': total_seconds,
            'Frames': d['frames']
        })

    return pd.DataFrame(result)


# --- Streamlit UI ---
st.set_page_config(page_title="Premiere XML → CSV", page_icon="🎬")
st.title("🎬 Анализатор XML из Adobe Premiere")
st.markdown("Загрузите XML-файл — получите CSV со сводкой длительности треков.")

uploaded_file = st.file_uploader("Выберите XML файл", type="xml")

fps = st.number_input("FPS (частота кадров)", min_value=1, max_value=120, value=25)

if uploaded_file is not None:
    try:
        df = parse_premiere_xml(uploaded_file, fps=fps)
        st.success(f"✅ Обнаружено {len(df)} треков")
        st.dataframe(df)

        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button(
            "⬇️ Скачать CSV",
            data=csv,
            file_name="tracks_duration.csv",
            mime="text/csv"
        )
    except Exception as e:
        st.error(f"Ошибка при обработке: {e}")
else:
    st.info("Загрузите XML, чтобы начать анализ.")
