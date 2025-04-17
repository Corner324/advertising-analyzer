import contextlib
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
import pandas as pd
from src.utils.logging import setup_logging
from tqdm import tqdm

setup_logging()

# Подавление логов OpenCV и FFmpeg
cv2.setLogLevel(0)
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_FFMPEG_LOG_LEVEL"] = "fatal"  # Изменено с "quiet" на "fatal"
os.environ["LIBAV_LOG_LEVEL"] = "0"  # Дополнительное подавление FFmpeg
os.environ["AV_LOG_LEVEL"] = "0"  # Дополнительное подавление FFmpeg

# Константы (дополнительно смягчены)
VIDEO_DIR = "videos"
MOCK_DATA_PATH = "Starbucks_predictions.json"
OUTPUT_FILE = "ad_quality_report.txt"
DEBUG_DIR = "debug_frames"
MIN_SIZE_RATIO = 0.003  # Снижено с 0.004
MIN_AREA = 2000  # Снижено с 3000
MAX_AREA = 200000  # Увеличено с 150000
MIN_CONFIDENCE = 0.7
ALLOWED_CLASSES = [4]  # Starbucks
IOU_THRESHOLD = 0.2  # Снижено с 0.3
MERGE_IOU_THRESHOLD = 0.15  # Снижено с 0.2
MAX_TIME_GAP_SECONDS = 4.0  # Увеличено с 3.0
MIN_DURATION = 0.05  # Снижено с 0.1

# Создаем папку для отладки
os.makedirs(DEBUG_DIR, exist_ok=True)


@dataclass
class BBox:
    x: int
    y: int
    width: int
    height: int


@dataclass
class AdMetrics:
    size_norm: float
    pos_score: float
    pos_label: str
    contrast_norm: float


@dataclass
class AdQuality:
    score: float
    label: str
    recommendation: str


@dataclass
class AdGroup:
    bbox: BBox
    frames: List[Tuple[int, Dict]]


class VideoProcessor:
    def __init__(self, video_path: str):
        self.video_path = video_path
        self.cap = None
        self.frame_rate = 0.0
        self.frame_width = 0
        self.frame_height = 0

    def initialize(self) -> bool:
        with suppress_outputs():
            if not os.path.exists(self.video_path):
                logging.error(f"Видеофайл не найден: {self.video_path}")
                return False
            # Применяем подавление ко всем операциям с VideoCapture
            self.cap = cv2.VideoCapture(self.video_path)
            if not self.cap.isOpened():
                logging.error(f"Не удалось открыть видео {self.video_path}")
                return False
            self.frame_rate = self.cap.get(cv2.CAP_PROP_FPS)
            self.frame_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            logging.info(
                f"Видео открыто: {self.video_path}, "
                f"разрешение={self.frame_width}x{self.frame_height}, FPS={self.frame_rate}"
            )
            return True

    def read_frame(self, frame_id: int) -> Optional[np.ndarray]:
        with suppress_outputs():
            if self.cap is None:
                logging.error("VideoCapture не инициализирован")
                return None
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ret, frame = self.cap.read()
            if not ret:
                logging.warning(f"Не удалось прочитать кадр {frame_id}")
                return None
            return frame

    def release(self):
        with suppress_outputs():
            if self.cap:
                self.cap.release()
                self.cap = None


@contextlib.contextmanager
def suppress_outputs():
    with open(os.devnull, "w") as fnull:
        old_stderr, old_stdout = sys.stderr, sys.stdout
        sys.stderr, sys.stdout = fnull, fnull
        try:
            yield
        finally:
            sys.stderr, sys.stdout = old_stderr, old_stdout


class BBoxValidator:
    @staticmethod
    def is_valid(bbox: Dict, frame_width: int, frame_height: int, confidence: float, class_id: int) -> bool:
        size = bbox["width"] * bbox["height"]
        size_norm = size / (frame_width * frame_height) if frame_width * frame_height > 0 else 0
        is_valid = (
            bbox["x"] >= 0
            and bbox["y"] >= 0
            and bbox["width"] > 0
            and bbox["height"] > 0
            and size_norm >= MIN_SIZE_RATIO
            and size >= MIN_AREA
            and size <= MAX_AREA
            and confidence >= MIN_CONFIDENCE
            and class_id in ALLOWED_CLASSES
        )
        if not is_valid:
            reasons = []
            if size_norm < MIN_SIZE_RATIO:
                reasons.append(f"size_norm={size_norm:.4f} < {MIN_SIZE_RATIO}")
            if size < MIN_AREA:
                reasons.append(f"area={size} < {MIN_AREA}")
            if size > MAX_AREA:
                reasons.append(f"area={size} > {MAX_AREA}")
            if confidence < MIN_CONFIDENCE:
                reasons.append(f"confidence={confidence:.2f} < {MIN_CONFIDENCE}")
            if class_id not in ALLOWED_CLASSES:
                reasons.append(f"class_id={class_id} не в {ALLOWED_CLASSES}")
            if bbox["x"] < 0 or bbox["y"] < 0:
                reasons.append("отрицательные координаты")
            if bbox["width"] <= 0 or bbox["height"] <= 0:
                reasons.append("нулевые размеры")
            logging.debug(f"Отфильтрован bbox {bbox}: {', '.join(reasons)}")
        return is_valid


class BBoxMetrics:
    @staticmethod
    def calculate_iou(bbox1: Dict, bbox2: Dict) -> float:
        x1, y1, w1, h1 = bbox1["x"], bbox1["y"], bbox1["width"], bbox1["height"]
        x2, y2, w2, h2 = bbox2["x"], bbox2["y"], bbox2["width"], bbox2["height"]
        x_left = max(x1, x2)
        y_top = max(y1, y2)
        x_right = min(x1 + w1, x2 + w2)
        y_bottom = min(y1 + h1, y2 + h2)
        if x_right < x_left or y_bottom < y_top:
            return 0.0
        intersection = (x_right - x_left) * (y_bottom - y_top)
        area1 = w1 * h1
        area2 = w2 * h2
        union = area1 + area2 - intersection
        return intersection / union if union > 0 else 0.0

    @staticmethod
    def to_bbox(bbox_dict: Dict) -> BBox:
        return BBox(x=bbox_dict["x"], y=bbox_dict["y"], width=bbox_dict["width"], height=bbox_dict["height"])

    @staticmethod
    def max_bbox(frames: List[Tuple[int, Dict]]) -> BBox:
        # Выбираем bbox с максимальной площадью
        bboxes = [frame[1] for frame in frames]
        areas = [b["width"] * b["height"] for b in bboxes]
        max_idx = np.argmax(areas)
        max_bbox = bboxes[max_idx]
        return BBox(
            x=max_bbox["x"],
            y=max_bbox["y"],
            width=max_bbox["width"],
            height=max_bbox["height"],
        )


class AdAnalyzer:
    @staticmethod
    def analyze(frame: np.ndarray, bbox: BBox, frame_width: int, frame_height: int, group_id: int) -> AdMetrics:
        # Увеличиваем отступ до 20% и проверяем границы
        padding = 0.2
        x_start = max(0, bbox.x - int(bbox.width * padding))
        y_start = max(0, bbox.y - int(bbox.height * padding))
        x_end = min(frame_width, bbox.x + bbox.width + int(bbox.width * padding))
        y_end = min(frame_height, bbox.y + bbox.height + int(bbox.height * padding))
        ad_region = frame[y_start:y_end, x_start:x_end]

        # Проверка на пустую область
        if ad_region.size == 0 or ad_region.shape[0] < 2 or ad_region.shape[1] < 2:
            logging.warning(
                f"Пустая или слишком маленькая область рекламы для группы {group_id}, bbox: {bbox.__dict__}"
            )
            ad_region = frame[bbox.y : bbox.y + bbox.height, bbox.x : bbox.x + bbox.width]
            if ad_region.size == 0:
                logging.error(f"Не удалось получить область рекламы для группы {group_id}")
                return AdMetrics(0.0, 0.0, "не определено", 0.0)

        size = bbox.width * bbox.height
        size_norm = size / (frame_width * frame_height)
        center_x = bbox.x + bbox.width / 2
        pos_score = 1 if abs(center_x - frame_width / 2) < 0.2 * frame_width else 0
        pos_label = "центр" if pos_score else "периферия"

        # Расчет контрастности (Michelson contrast)
        gray = cv2.cvtColor(ad_region, cv2.COLOR_BGR2GRAY)
        min_intensity = np.min(gray)
        max_intensity = np.max(gray)
        if max_intensity == min_intensity:
            contrast_norm = 0.0
        else:
            contrast_norm = (max_intensity - min_intensity) / (max_intensity + min_intensity)
        contrast_norm = min(contrast_norm, 1.0)  # type: ignore

        # Сохраняем кадр для отладки
        frame_copy = frame.copy()
        cv2.rectangle(frame_copy, (bbox.x, bbox.y), (bbox.x + bbox.width, bbox.y + bbox.height), (0, 255, 0), 2)
        cv2.putText(
            frame_copy,
            f"Size: {size_norm:.2%}, Contrast: {contrast_norm:.2f}",
            (bbox.x, bbox.y - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 255, 0),
            2,
        )
        cv2.imwrite(os.path.join(DEBUG_DIR, f"group_{group_id}.jpg"), frame_copy)

        logging.debug(
            f"Группа {group_id}: size_norm={size_norm:.4f}, pos_score={pos_score}, "
            f"contrast_norm={contrast_norm:.2f}"
        )
        return AdMetrics(size_norm, pos_score, pos_label, contrast_norm)

    @staticmethod
    def evaluate_quality(metrics: AdMetrics, duration: float) -> AdQuality:
        duration_norm = min(duration / 3, 1.0)  # Смягчено с /5 до /3
        score = 0.3 * metrics.size_norm + 0.3 * metrics.pos_score + 0.2 * metrics.contrast_norm + 0.2 * duration_norm
        if score < 0.5:
            label = "низкое"
            recommendation = "Увеличьте размер, контрастность или длительность."
        elif score < 0.75:
            label = "среднее"
            recommendation = "Попробуйте переместить в центр или улучшить контрастность."
        else:
            label = "высокое"
            recommendation = "Параметры оптимальны, сохраните текущие настройки."
        logging.debug(f"Оценка качества: score={score:.2f}, label={label}, duration_norm={duration_norm:.2f}")
        return AdQuality(score, label, recommendation)


class AdGroupProcessor:
    def __init__(self, frame_rate: float, frame_width: int, frame_height: int):
        self.frame_rate = frame_rate
        self.frame_width = frame_width
        self.frame_height = frame_height

    def group_ads(self, frames_data: List[Dict]) -> List[AdGroup]:
        validator = BBoxValidator()
        metrics = BBoxMetrics()
        ad_groups = []
        logging.debug(f"Начало группировки, кадров: {len(frames_data)}")
        for frame_data in tqdm(frames_data, desc="Группировка кадров"):
            frame_id = frame_data["frame_id"]
            for ad in frame_data["ads"]:
                bbox = ad["bbox"]
                confidence = ad.get("confidence", 1.0)
                class_id = ad.get("class_id", -1)
                logging.debug(f"Кадр {frame_id}, bbox: {bbox}, confidence: {confidence:.2f}, class_id: {class_id}")
                if not validator.is_valid(bbox, self.frame_width, self.frame_height, confidence, class_id):
                    continue
                found_group = False
                for group in ad_groups:
                    if metrics.calculate_iou(bbox, group.bbox.__dict__) > IOU_THRESHOLD:
                        group.frames.append((frame_id, bbox))
                        found_group = True
                        break
                if not found_group:
                    ad_groups.append(AdGroup(metrics.to_bbox(bbox), [(frame_id, bbox)]))
        logging.info(f"Сформировано {len(ad_groups)} начальных групп")
        return self.merge_groups(ad_groups)

    def merge_groups(self, ad_groups: List[AdGroup]) -> List[AdGroup]:
        metrics = BBoxMetrics()
        ad_groups.sort(key=lambda g: min(f[0] for f in g.frames))
        merged_groups = []
        for group in ad_groups:
            if not merged_groups:
                merged_groups.append(group)
                continue
            last_group = merged_groups[-1]
            last_max_frame = max(f[0] for f in last_group.frames)
            current_min_frame = min(f[0] for f in group.frames)
            if (current_min_frame - last_max_frame) <= self.frame_rate * MAX_TIME_GAP_SECONDS and metrics.calculate_iou(
                last_group.bbox.__dict__, group.bbox.__dict__
            ) > MERGE_IOU_THRESHOLD:
                last_group.frames.extend(group.frames)
                last_group.bbox = metrics.max_bbox(last_group.frames)  # Используем max_bbox
            else:
                merged_groups.append(group)
        logging.info(f"После объединения: {len(merged_groups)} групп")
        return merged_groups

    def process_groups(self, groups: List[AdGroup], video_processor: VideoProcessor) -> List[str]:
        analyzer = AdAnalyzer()
        results = []
        for group_id, group in enumerate(tqdm(groups, desc="Анализ групп рекламы")):
            frame_ids = [f[0] for f in group.frames]
            duration = (max(frame_ids) - min(frame_ids) + 1) / self.frame_rate if frame_ids else 0.0
            if duration < MIN_DURATION:
                logging.debug(f"Пропущена группа с длительностью {duration:.2f} сек")
                continue
            frame = video_processor.read_frame(frame_ids[0])
            if frame is None:
                continue
            metrics = analyzer.analyze(frame, group.bbox, self.frame_width, self.frame_height, group_id)
            quality = analyzer.evaluate_quality(metrics, duration)
            result = (
                f"Реклама в видео {os.path.basename(video_processor.video_path)}:\n"
                f"  - Положение: {metrics.pos_label}\n"
                f"  - Размер: {metrics.size_norm:.2%} от кадра\n"
                f"  - Контрастность: {metrics.contrast_norm:.2f}\n"
                f"  - Длительность: {duration:.1f} сек\n"
                f"  - Оценка качества: {quality.label} (балл: {quality.score:.2f})\n"
                f"  - Рекомендация: {quality.recommendation}\n"
            )
            results.append(result)
            logging.info(
                f"Группа {group_id}: кадры {min(frame_ids)}-{max(frame_ids)}, "
                f"длительность {duration:.1f} сек, размер {metrics.size_norm:.2%}, "
                f"bbox {group.bbox.__dict__}"
            )
        return results


class AdQualityAnalyzer:
    def __init__(self, debug_dir: str):
        self.results = []
        self.debug_dir = debug_dir
        os.makedirs(self.debug_dir, exist_ok=True)

    def process_video(self, video_path: str, predictions_path: str) -> List[str]:
        video_processor = VideoProcessor(video_path)
        if not video_processor.initialize():
            return []

        mock_data_df = pd.read_json(predictions_path, encoding="utf-8")
        video_data = mock_data_df.to_dict(orient="records")[0]  # Предполагаем один видеофайл

        group_processor = AdGroupProcessor(
            video_processor.frame_rate, video_processor.frame_width, video_processor.frame_height
        )
        ad_groups = group_processor.group_ads(video_data["frames"])
        results = group_processor.process_groups(ad_groups, video_processor)
        video_processor.release()
        return results

    def save_report(self, results: List[str], output_file: str):
        with open(output_file, "w", encoding="utf-8") as f:
            f.write("Отчет по качеству отображения рекламы\n\n")
            f.write("\n".join(results))
        logging.info(f"Отчет сохранен: {len(results)} записей")
        print(f"Результаты записаны в {output_file}")
