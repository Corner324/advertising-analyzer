import json
import os

import cv2
from ultralytics import YOLO


class YoloDetector:
    def __init__(self, model_path: str, output_dir: str = "yolo_frames"):
        self.model = YOLO(model_path).to("cpu")  # Пока CPU, для GPU можно изменить
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)
        self.conf_threshold = 0.7
        self.min_bbox_area = 4000
        self.max_bbox_area = 150000
        self.allowed_classes = [4]  # Starbucks

    def predict_video(self, video_path: str, output_json: str) -> bool:
        if not os.path.isfile(video_path):
            print(f"Файл {video_path} не найден.")
            return False

        print(f"Обработка видео: {os.path.basename(video_path)}...")
        results = self.model.predict(source=video_path, conf=self.conf_threshold, save=False, verbose=False)

        video_data = {"video_id": os.path.basename(video_path), "frames": []}

        cap = cv2.VideoCapture(video_path)
        frame_rate = cap.get(cv2.CAP_PROP_FPS)

        for frame_id, result in enumerate(results):
            frame_ads = []
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ret, frame = cap.read()
            if not ret:
                print(f"Не удалось прочитать кадр {frame_id}")
                continue

            for box in result.boxes:
                xyxy = box.xyxy[0].tolist()
                conf = float(box.conf[0].item())
                cls = int(box.cls[0].item())

                if cls not in self.allowed_classes:
                    print(f"Кадр {frame_id}: Пропущен bbox, class_id={cls}")
                    continue

                bbox = {
                    "x": int(xyxy[0]),
                    "y": int(xyxy[1]),
                    "width": int(xyxy[2] - xyxy[0]),
                    "height": int(xyxy[3] - xyxy[1]),
                }

                area = bbox["width"] * bbox["height"]
                if area < self.min_bbox_area or area > self.max_bbox_area:
                    print(f"Кадр {frame_id}: Пропущен bbox, area={area}")
                    continue

                ad = {"type": "direct", "bbox": bbox, "confidence": round(conf, 2), "class_id": cls}
                frame_ads.append(ad)

                # Сохраняем кадр для отладки
                cv2.rectangle(
                    frame,
                    (bbox["x"], bbox["y"]),
                    (bbox["x"] + bbox["width"], bbox["y"] + bbox["height"]),
                    (0, 255, 0),
                    2,
                )
                cv2.imwrite(os.path.join(self.output_dir, f"frame_{frame_id:04d}.jpg"), frame)

            video_data["frames"].append({"frame_id": frame_id, "ads": frame_ads})

        cap.release()

        # Сохраняем JSON
        with open(output_json, "w", encoding="utf-8") as f:
            json.dump([video_data], f, indent=2)

        print(f"Предсказания сохранены в {output_json}")
        return True
