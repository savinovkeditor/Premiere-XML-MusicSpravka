import xml.etree.ElementTree as ET
from collections import OrderedDict
import csv
import os
import re

# автор: Савинов Кирилл
# для связи, вопросов и предложений можно связаться со мной по почте savinov.k.editor@gmail.com

def parse_track_name(filename):
    """
    Разделяет имя файла на:
    - технический префикс (до названия трека)
    - название трека
    - автора
    Пример:
        apollomedia_gtpm_153_12_thin-margins_oliver-spencer-robin-kent.mp3 ->
        ('apollomedia_gtpm_153_12_', 'Thin Margins', 'Oliver Spencer Robin Kent')
    """
    name = filename.rsplit('.', 1)[0]
    parts = name.split('_')

    # Поиск последней части, где встречается '-'
    # Всё после неё — автор, перед — название, до этого — префикс
    for i in range(len(parts)-1, -1, -1):
        if '-' in parts[i]:
            author_raw = parts[i]
            track_parts = parts[:i]
            break
    else:
        author_raw = ''
        track_parts = parts

    # Префикс — всё до первых 3–4 технических сегментов, где обычно цифры
    prefix_match = re.match(r'^([a-zA-Z]+_[a-zA-Z0-9]+_[0-9_]+_)', name)
    prefix = prefix_match.group(1) if prefix_match else '_'.join(parts[:3]) + '_'

    # Отделяем название трека от префикса
    track_core = name[len(prefix):].rsplit('_', 1)[0] if prefix else track_parts[-1]
    track_core = track_core.replace('-', ' ').replace('_', ' ').strip().title()

    # Обработка автора
    author_name = author_raw.replace('-', ' ').replace('_', ' ').strip().title() if author_raw else ''

    return prefix, track_core, author_name


def seconds_to_hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{int(h):02}:{int(m):02}:{int(s):02}"


def parse_premiere_xml(xml_file, fps=25):
    """Парсит XML, суммирует длительности треков и игнорирует дубли по linkclipref"""
    if not os.path.exists(xml_file):
        raise FileNotFoundError(f"Файл XML '{xml_file}' не найден!")

    tree = ET.parse(xml_file)
    root = tree.getroot()

    tracks_data = OrderedDict()
    seen_linked = set()

    for clip in root.iter("clipitem"):
        # игнорируем дубли аудиоканалов
        link_refs = [l.text.strip() for l in clip.findall("link/linkclipref") if l.text]
        if any(ref in seen_linked for ref in link_refs):
            continue
        for ref in link_refs:
            seen_linked.add(ref)
        seen_linked.add(clip.attrib.get("id", ""))

        # имя файла
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

        # in/out
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

    # переводим в секунды
    result = OrderedDict()
    for (prefix, track), d in tracks_data.items():
        total_seconds = round(d['frames'] / fps)
        result[(prefix, track)] = {
            'prefix': prefix,
            'track': track,
            'author': d['author'],
            'count': d['count'],
            'frames': d['frames'],
            'seconds': total_seconds,
            'hms': seconds_to_hms(total_seconds)
        }

    return result


def export_to_csv(tracks_result, output_file="tracks_duration.csv"):
    """Экспорт в CSV"""
    with open(output_file, "w", newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["Prefix", "Track", "Author", "Repeats", "Duration (HH:MM:SS)", "Seconds", "Frames"])
        for (prefix, track), info in tracks_result.items():
            writer.writerow([
                info['prefix'],
                info['track'],
                info['author'],
                info['count'],
                info['hms'],
                info['seconds'],
                info['frames']
            ])
    print(f"✅ CSV сохранён: {output_file}")


if __name__ == "__main__":
    xml_path = "project.xml"  # путь к XML
    result = parse_premiere_xml(xml_path, fps=25)
    export_to_csv(result, "tracks_duration.csv")

    print("\nРезультат:")
    for i, ((prefix, track), info) in enumerate(result.items(), start=1):
        print(f"{i:02}. [{prefix}] {track} — {info['hms']} ({info['author']}) ×{info['count']}")
