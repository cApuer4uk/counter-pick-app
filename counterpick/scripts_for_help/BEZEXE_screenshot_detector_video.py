import os
import cv2
import json
from datetime import datetime
from ultralytics import YOLO

# === Пути под твою текущую структуру (scripts_for_help/...) ===
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SAVE_DIR = os.path.join(BASE_DIR, 'tmp_screenshots')            # тут лежат скриншоты
MODEL_PATH = os.path.join(BASE_DIR, '..', 'weights', 'best.pt') # веса YOLO
COUNTERS_PATH = os.path.join(BASE_DIR, '..', 'db', 'counters.json')  # counters.json

# === Параметры модели ===
imgsz = 640
conf = 0.3
iou = 0.4

# === Видео-вывод ===
timestamp = datetime.now().strftime('%Y-%m-%d_%H-%M-%S')
video_output_path = os.path.join(BASE_DIR, f'detected_{timestamp}.mp4')
video_fps = 5
video_writer = None

# === Проверки путей ===
os.makedirs(SAVE_DIR, exist_ok=True)

# === Загрузка модели и контрпиков ===
model = YOLO(MODEL_PATH)
with open(COUNTERS_PATH, 'r', encoding='utf-8') as f:
    counters_data = json.load(f)

def get_counter_names(hero_label: str):
    for entry in counters_data:
        if entry["hero"] == hero_label:
            return [c["counter"] for c in entry["counters"]]
    return []

# === Собираем список изображений один раз (офлайн-прогон) ===
files = sorted(
    [f for f in os.listdir(SAVE_DIR) if f.lower().endswith(('.png', '.jpg', '.jpeg'))],
    key=lambda x: os.path.getctime(os.path.join(SAVE_DIR, x))
)

if not files:
    print(f'Пусто в {SAVE_DIR}. Сначала накидай скринов.')
    raise SystemExit(0)

print(f'Найдено {len(files)} скринов. Делаю видео: {video_output_path}')

try:
    for name in files:
        filepath = os.path.join(SAVE_DIR, name)
        img = cv2.imread(filepath)
        if img is None:
            print(f"⚠️ Пропуск: не читается {name}")
            continue

        frame = img.copy()

        # Предикт
        results = model.predict(
            source=img,
            imgsz=imgsz,
            conf=conf,
            iou=iou,
            verbose=False
        )
        r = results[0]
        boxes = r.boxes

        # Отрисовка боксов + подписей
        if boxes is not None and len(boxes) > 0:
            for box in boxes:
                cls_id = int(box.cls[0])
                x1, y1, x2, y2 = box.xyxy[0].cpu().numpy().astype(int)
                label = model.names[cls_id]

                # Рамка и подпись класса
                cv2.rectangle(frame, (x1, y1), (x2, y2), (40, 220, 40), 2)

                # Доверие (conf) — крупнее и жирнее
                conf_value = float(box.conf[0])
                text = f"{label} {int(conf_value * 100)}%"
                font_scale = 0.8  # было 0.55 → крупнее
                thickness = 2  # было 1 → жирнее
                tsize, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                cv2.putText(frame, text, (x1 + 5, y1 + tsize[1] + 5),
                            cv2.FONT_HERSHEY_SIMPLEX, font_scale, (40, 220, 40), thickness)

                # Контрпики (до 4)
                counters = get_counter_names(label)[:4]
                if counters:
                    box_h = max(1, y2 - y1)
                    spacing = box_h // (len(counters) + 1)
                    font_scale = 0.55
                    thickness = 1

                    # Если герой правее центра — пишем слева, иначе справа
                    box_center_x = (x1 + x2) // 2
                    draw_left = box_center_x > frame.shape[1] // 2

                    for i, cname in enumerate(counters):
                        cy = y1 + spacing * (i + 1)
                        tsize, _ = cv2.getTextSize(cname, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness)
                        if draw_left:
                            cx = x1 - tsize[0] - 12
                        else:
                            cx = x2 + 12
                        cv2.putText(frame, cname, (cx, cy),
                                    cv2.FONT_HERSHEY_SIMPLEX, font_scale, (0, 160, 255), thickness)
        else:
            print(f'👻 На {name} героев не найдено.')

        # Инициализация видео на первом кадре
        if video_writer is None:
            h, w = frame.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*'mp4v')
            video_writer = cv2.VideoWriter(video_output_path, fourcc, video_fps, (w, h))

        # Запись кадра
        video_writer.write(frame)

finally:
    if video_writer is not None:
        video_writer.release()
        print(f'🎥 Видео сохранено: {video_output_path}')

print('Готово. Скриншоты НЕ удалялись.')
