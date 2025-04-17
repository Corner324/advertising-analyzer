import contextlib
import json
import logging
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.spatial import cKDTree
from src.utils.logging import setup_logging


setup_logging(level=logging.INFO)  # Уменьшаем уровень логирования

# Подавление логов OpenCV и FFmpeg
cv2.setLogLevel(0)
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_FFMPEG_LOG_LEVEL"] = "fatal"
os.environ["LIBAV_LOG_LEVEL"] = "0"
os.environ["AV_LOG_LEVEL"] = "0"

# Константы
VIDEO_DIR = "videos"
MOCK_DATA_PATH = "Starbucks_predictions.json"
OUTPUT_FILE = "ad_quality_report.txt"
MIN_SIZE_RATIO = 0.003
MIN_AREA = 2000
MAX_AREA = 200000
MIN_CONFIDENCE = 0.7
ALLOWED_CLASSES = [4]  # Starbucks
IOU_THRESHOLD = 0.2
MERGE_IOU_THRESHOLD = 0.15
MAX_TIME_GAP_SECONDS = 4.0
MIN_DURATION = 0.05
FRAME_SKIP = 5  # Анализируем каждый 5-й кадр


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
        self.frame_cache = {}  # Кэш кадров

    def initialize(self) -> bool:
        with suppress_outputs():
            if not os.path.exists(self.video_path):
                logging.error(f"Видеофайл не найден: {self.video_path}")
                return False
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
            if frame_id in self.frame_cache:
                return self.frame_cache[frame_id]
            self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
            ret, frame = self.cap.read()
            if not ret:
                logging.warning(f"Не удалось прочитать кадр {frame_id}")
                return None
            # Масштабируем кадр для ускорения анализа
            frame = cv2.resize(frame, (640, 360))
            self.frame_cache[frame_id] = frame
            return frame

    def release(self):
        with suppress_outputs():
            if self.cap:
                self.cap.release()
                self.cap = None
            self.frame_cache.clear()


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
        return (
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
        padding = 0.2
        x_start = max(0, bbox.x - int(bbox.width * padding))
        y_start = max(0, bbox.y - int(bbox.height * padding))
        x_end = min(frame_width, bbox.x + bbox.width + int(bbox.width * padding))
        y_end = min(frame_height, bbox.y + bbox.height + int(bbox.height * padding))
        ad_region = frame[y_start:y_end, x_start:x_end]

        if ad_region.size == 0 or ad_region.shape[0] < 2 or ad_region.shape[1] < 2:
            logging.warning(f"Пустая область рекламы для группы {group_id}")
            ad_region = frame[bbox.y : bbox.y + bbox.height, bbox.x : bbox.x + bbox.width]
            if ad_region.size == 0:
                return AdMetrics(0.0, 0.0, "не определено", 0.0)

        size = bbox.width * bbox.height
        size_norm = size / (frame_width * frame_height)
        center_x = bbox.x + bbox.width / 2
        pos_score = 1 if abs(center_x - frame_width / 2) < 0.2 * frame_width else 0
        pos_label = "центр" if pos_score else "периферия"

        gray = cv2.cvtColor(ad_region, cv2.COLOR_BGR2GRAY)
        min_intensity = np.min(gray)
        max_intensity = np.max(gray)
        contrast_norm = (
            0.0 if max_intensity == min_intensity else (max_intensity - min_intensity) / (max_intensity + min_intensity)
        )
        contrast_norm = min(contrast_norm, 1.0)

        return AdMetrics(size_norm, pos_score, pos_label, contrast_norm)

    @staticmethod
    def evaluate_quality(metrics: AdMetrics, duration: float) -> AdQuality:
        duration_norm = min(duration / 3, 1.0)
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
        # Предварительная фильтрация bbox’ов
        valid_bboxes = []
        for frame_data in frames_data:
            frame_id = frame_data["frame_id"]
            if frame_id % FRAME_SKIP != 0:  # Пропускаем кадры
                continue
            for ad in frame_data["ads"]:
                bbox = ad["bbox"]
                confidence = ad.get("confidence", 1.0)
                class_id = ad.get("class_id", -1)
                if validator.is_valid(bbox, self.frame_width, self.frame_height, confidence, class_id):
                    valid_bboxes.append((frame_id, bbox))
        # Пространственная индексация
        if valid_bboxes:
            centers = np.array([[b[1]["x"] + b[1]["width"] / 2, b[1]["y"] + b[1]["height"] / 2] for b in valid_bboxes])
            tree = cKDTree(centers)
            for i, (frame_id, bbox) in enumerate(valid_bboxes):
                found_group = False
                # Ищем только ближайшие bbox’ы
                indices = tree.query_ball_point([bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2], r=200)
                for j in indices:
                    if j >= i:
                        continue
                    other_frame_id, other_bbox = valid_bboxes[j]
                    if metrics.calculate_iou(bbox, other_bbox) > IOU_THRESHOLD:
                        for group in ad_groups:
                            if any(
                                f[0] == other_frame_id and metrics.calculate_iou(f[1], other_bbox) > IOU_THRESHOLD
                                for f in group.frames
                            ):
                                group.frames.append((frame_id, bbox))
                                found_group = True
                                break
                        if found_group:
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
                last_group.bbox = metrics.max_bbox(last_group.frames)
            else:
                merged_groups.append(group)
        logging.info(f"После объединения: {len(merged_groups)} групп")
        return merged_groups

    def process_groups(self, groups: List[AdGroup], video_processor: VideoProcessor) -> List[str]:
        analyzer = AdAnalyzer()
        results = []

        def process_group(group_id, group):
            frame_ids = [f[0] for f in group.frames]
            duration = (max(frame_ids) - min(frame_ids) + 1) / self.frame_rate if frame_ids else 0.0
            if duration < MIN_DURATION:
                return None
            frame = video_processor.read_frame(frame_ids[0])
            if frame is None:
                return None
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
            logging.info(
                f"Группа {group_id}: кадры {min(frame_ids)}-{max(frame_ids)}, "
                f"длительность {duration:.1f} сек, размер {metrics.size_norm:.2%}"
            )
            return result

        # Параллельная обработка групп
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(process_group, i, g) for i, g in enumerate(groups)]
            for future in futures:
                result = future.result()
                if result:
                    results.append(result)
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
        # Чтение JSON без Pandas
        with open(predictions_path, "r", encoding="utf-8") as f:
            video_data = json.load(f)[0]  # Предполагаем один видеофайл
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
