import contextlib
import json
import logging
import os
import sys
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np
from scipy.spatial import cKDTree
from sklearn.cluster import DBSCAN
from src.utils.logging import setup_logging
from tqdm import tqdm

setup_logging(level=logging.INFO)

cv2.setLogLevel(0)
os.environ["OPENCV_LOG_LEVEL"] = "FATAL"
os.environ["OPENCV_FFMPEG_LOG_LEVEL"] = "fatal"
os.environ["LIBAV_LOG_LEVEL"] = "0"
os.environ["AV_LOG_LEVEL"] = "0"
os.environ["FFMPEG_THREADS"] = "1"

VIDEO_DIR = "videos"
MOCK_DATA_PATH = "Starbucks_predictions.json"
OUTPUT_FILE = "ad_quality_report.txt"
MIN_SIZE_RATIO = 0.003
MIN_AREA = 1000
MAX_AREA = 200000
MIN_CONFIDENCE = 0.7
ALLOWED_CLASSES = [0, 1, 2, 3, 4]
IOU_THRESHOLD = 0.2
MERGE_IOU_THRESHOLD = 0.15
MAX_TIME_GAP_SECONDS = 1.0
MIN_DURATION = 0.05
FRAME_SKIP = 5
MAX_CACHE_SIZE = 10


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
        self.frame_cache = {}
        self.frame_count = 0
        self.scale_width = 640
        self.scale_height = 360

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
            self.frame_count = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
            if self.frame_count <= 0 or self.frame_rate <= 0:
                logging.error(f"Некорректное видео: кадров={self.frame_count}, FPS={self.frame_rate}")
                self.cap.release()
                return False
            logging.info(
                f"Видео открыто: {self.video_path}, "
                f"разрешение={self.frame_width}x{self.frame_height}, FPS={self.frame_rate}, кадров={self.frame_count}"
            )
            return True

    def read_frame(self, frame_id: int) -> Optional[np.ndarray]:
        with suppress_outputs():
            if self.cap is None:
                logging.error("VideoCapture не инициализирован")
                return None
            if frame_id >= self.frame_count:
                logging.warning(f"Кадр {frame_id} превышает количество кадров ({self.frame_count})")
                return None
            if frame_id in self.frame_cache:
                logging.debug(f"Кадр {frame_id} взят из кэша")
                return self.frame_cache[frame_id]
            try:
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame_id)
                ret, frame = self.cap.read()
                if not ret:
                    logging.warning(f"Не удалось прочитать кадр {frame_id}")
                    return None
                frame = cv2.resize(frame, (self.scale_width, self.scale_height))
                if len(self.frame_cache) >= MAX_CACHE_SIZE:
                    oldest_frame = min(self.frame_cache.keys())
                    del self.frame_cache[oldest_frame]
                self.frame_cache[frame_id] = frame
                logging.debug(f"Кадр {frame_id} добавлен в кэш, размер кэша: {len(self.frame_cache)}")
                return frame
            except Exception as e:
                logging.error(f"Ошибка чтения кадра {frame_id}: {str(e)}")
                return None

    def scale_bbox(self, bbox: BBox) -> BBox:
        scale_x = self.scale_width / self.frame_width
        scale_y = self.scale_height / self.frame_height
        return BBox(
            x=int(bbox.x * scale_x),
            y=int(bbox.y * scale_y),
            width=int(bbox.width * scale_x),
            height=int(bbox.height * scale_y),
        )

    def release(self):
        with suppress_outputs():
            if self.cap:
                self.cap.release()
                self.cap = None
            self.frame_cache.clear()
            logging.debug("VideoCapture освобождён, кэш очищен")


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
        valid = (
            bbox["x"] >= 0
            and bbox["y"] >= 0
            and bbox["x"] + bbox["width"] <= frame_width
            and bbox["y"] + bbox["height"] <= frame_height
            and bbox["width"] > 0
            and bbox["height"] > 0
            and size_norm >= MIN_SIZE_RATIO
            and size >= MIN_AREA
            and size <= MAX_AREA
            and confidence >= MIN_CONFIDENCE
            and class_id in ALLOWED_CLASSES
        )
        if not valid:
            logging.info(
                f"Невалидный bbox: x={bbox['x']}, y={bbox['y']}, width={bbox['width']}, height={bbox['height']}, "
                f"size={size}, size_norm={size_norm}, confidence={confidence}, class_id={class_id}, "
                f"frame_width={frame_width}, frame_height={frame_height}"
            )
        return valid


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
    def __init__(self, original_frame_width: int, original_frame_height: int):
        """
        Инициализация анализатора рекламы.

        Args:
            original_frame_width (int): Оригинальная ширина кадра (например, 1280).
            original_frame_height (int): Оригинальная высота кадра (например, 720).
        """
        self.original_frame_width = original_frame_width
        self.original_frame_height = original_frame_height
        self.padding = 0.2  # Отступ для анализа области вокруг bbox

    def analyze(self, frame, bbox):
        """
        Анализирует кадр и bbox для получения метрик рекламы.

        Args:
            frame (np.ndarray): Кадр в формате RGB.
            bbox (dict): Словарь с ключами 'x', 'y', 'width', 'height'.

        Returns:
            dict: Метрики рекламы (size_norm, contrast_norm, position_score, pos_label).
        """
        import cv2
        import numpy as np

        # Извлечение координат и размеров bbox
        x, y, width, height = bbox["x"], bbox["y"], bbox["width"], bbox["height"]

        # Рассчитываем нормализованный размер (size_norm) с использованием оригинальных размеров кадра
        size = width * height
        frame_area = self.original_frame_width * self.original_frame_height
        size_norm = size / frame_area if frame_area > 0 else 0.0

        # Рассчитываем позицию (центр или периферия)
        center_x = x + width / 2
        center_y = y + height / 2
        pos_score = (
            1.0
            if (
                abs(center_x - self.original_frame_width / 2) < 0.2 * self.original_frame_width
                and abs(center_y - self.original_frame_height / 2) < 0.2 * self.original_frame_height
            )
            else 0.5
        )
        pos_label = "центр" if pos_score == 1.0 else "периферия"

        # Определяем область для анализа контрастности (с padding)
        x_start = max(0, int(x - width * self.padding))
        y_start = max(0, int(y - height * self.padding))
        x_end = min(frame.shape[1], int(x + width * (1 + self.padding)))
        y_end = min(frame.shape[0], int(y + height * (1 + self.padding)))

        # Проверяем, что область не пуста
        if x_end <= x_start or y_end <= y_start:
            contrast_norm = 0.0
        else:
            # Извлекаем область для анализа
            ad_region = frame[y_start:y_end, x_start:x_end]
            if ad_region.size == 0:
                contrast_norm = 0.0
            else:
                # Преобразуем в градации серого для анализа контрастности
                gray = cv2.cvtColor(ad_region, cv2.COLOR_RGB2GRAY)
                min_intensity = np.min(gray)
                max_intensity = np.max(gray)
                contrast_norm = (max_intensity - min_intensity) / (max_intensity + min_intensity + 1e-6)

        return {
            "size_norm": size_norm,
            "contrast_norm": contrast_norm,
            "position_score": pos_score,
            "pos_label": pos_label,
        }

    @staticmethod
    def evaluate_quality(metrics, duration: float):
        """
        Оценивает качество рекламы на основе метрик и длительности.

        Args:
            metrics (dict): Метрики из метода analyze.
            duration (float): Длительность группы в секундах.

        Returns:
            AdQuality: Объект с оценкой качества, меткой и рекомендацией.
        """
        duration_norm = min(duration / 3, 1.0)
        score = (
            0.3 * metrics["size_norm"]
            + 0.3 * metrics["position_score"]
            + 0.2 * metrics["contrast_norm"]
            + 0.2 * duration_norm
        )
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
        self.max_time_gap_seconds = 2.0  # Увеличено с 1.0 до 2.0

    def group_ads(self, frames_data: List[Dict]) -> List[AdGroup]:
        validator = BBoxValidator()
        metrics = BBoxMetrics()
        valid_bboxes = []
        for frame_data in frames_data:
            frame_id = frame_data["frame_id"]
            if frame_id % FRAME_SKIP != 0:
                continue
            for ad in frame_data["ads"]:
                bbox = ad["bbox"]
                confidence = ad.get("confidence", 1.0)
                class_id = ad.get("class_id", -1)
                if validator.is_valid(bbox, self.frame_width, self.frame_height, confidence, class_id):
                    valid_bboxes.append((frame_id, bbox))
                else:
                    logging.debug(f"Отфильтрован некорректный bbox: {bbox}")

        if not valid_bboxes:
            return []

        # Пространственно-временная кластеризация с DBSCAN
        features = np.array(
            [
                [
                    frame_id / self.frame_rate,  # Время в секундах
                    bbox["x"] + bbox["width"] / 2,  # Центр по x
                    bbox["y"] + bbox["height"] / 2,  # Центр по y
                ]
                for frame_id, bbox in valid_bboxes
            ]
        )
        # Нормализация для DBSCAN
        features = (features - features.mean(axis=0)) / (features.std(axis=0) + 1e-6)
        clustering = DBSCAN(eps=0.5, min_samples=3).fit(features)
        labels = clustering.labels_

        ad_groups = []
        for label in set(labels):
            if label == -1:  # Пропускаем шум
                continue
            group_frames = [(frame_id, bbox) for (frame_id, bbox), l in zip(valid_bboxes, labels) if l == label]
            if group_frames:
                ad_groups.append(AdGroup(metrics.max_bbox(group_frames), group_frames))

        logging.info(f"Сформировано {len(ad_groups)} групп с DBSCAN")
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

    def process_groups(self, groups: List[AdGroup], video_processor: VideoProcessor, filename: str) -> List[str]:
        # Инициализируем AdAnalyzer с оригинальными размерами кадра
        analyzer = AdAnalyzer(original_frame_width=self.frame_width, original_frame_height=self.frame_height)
        results = []
        for group_id, group in enumerate(tqdm(groups, desc="Анализ групп рекламы")):
            frame_ids = [f[0] for f in group.frames]
            duration = (max(frame_ids) - min(frame_ids) + 1) / self.frame_rate if frame_ids else 0.0
            if duration < MIN_DURATION:
                logging.info(f"Пропущена группа {group_id} с длительностью {duration:.2f} сек")
                continue
            frame = video_processor.read_frame(frame_ids[0])
            if frame is None:
                logging.warning(f"Не удалось обработать группу {group_id}: кадр не прочитан")
                continue
            # Используем оригинальный bbox без масштабирования, так как size_norm рассчитывается в оригинальных координатах
            bbox = group.bbox.__dict__
            metrics = analyzer.analyze(frame, bbox)
            quality = analyzer.evaluate_quality(metrics, duration)
            result = (
                f"Реклама в видео {filename}:\n"
                f"  - Положение: {metrics['pos_label']}\n"
                f"  - Размер: {metrics['size_norm']:.2%} от кадра\n"
                f"  - Контрастность: {metrics['contrast_norm']:.2f}\n"
                f"  - Длительность: {duration:.1f} сек\n"
                f"  - Оценка качества: {quality.label} (балл: {quality.score:.2f})\n"
                f"  - Рекомендация: {quality.recommendation}\n"
            )
            results.append(result)
            logging.info(
                f"Группа {group_id}: кадры {min(frame_ids)}-{max(frame_ids)}, "
                f"длительность {duration:.1f} сек, размер {metrics['size_norm']:.2%}"
            )
        return results


class AdQualityAnalyzer:
    def __init__(self, debug_dir: str):
        self.results = []
        self.debug_dir = debug_dir
        os.makedirs(self.debug_dir, exist_ok=True)
        self.frame_rate = None  # Инициализируем frame_rate как None

    def process_video(self, video_path: str, predictions_path: str, filename: str) -> List[str]:
        try:
            video_processor = VideoProcessor(video_path)
            if not video_processor.initialize():
                logging.error("Не удалось инициализировать видео")
                return []
            # Сохраняем frame_rate из video_processor
            self.frame_rate = video_processor.frame_rate
            with open(predictions_path, "r", encoding="utf-8") as f:
                video_data = json.load(f)[0]
            group_processor = AdGroupProcessor(
                video_processor.frame_rate, video_processor.frame_width, video_processor.frame_height
            )
            ad_groups = group_processor.group_ads(video_data["frames"])
            results = group_processor.process_groups(ad_groups, video_processor, filename)
            video_processor.release()
            return results
        except Exception as e:
            logging.error(f"Ошибка обработки видео {video_path}: {str(e)}")
            return []

    def save_report(self, results: List[str], output_file: str):
        try:
            if self.frame_rate is None or self.frame_rate <= 0:
                logging.error("Frame rate не определён или некорректен")
                raise ValueError("Frame rate не установлен")

            # Сохраняем текстовый отчёт
            with open(output_file, "w", encoding="utf-8") as f:
                f.write("Отчет по качеству отображения рекламы\n\n")
                f.write("\n".join(results))
            # Сохраняем JSON для отладки
            json_report = []
            for i, r in enumerate(results):
                try:
                    # Извлекаем номера кадров из строки лога
                    frame_info = r.split("Длительность:")[0].split("кадры ")[1]
                    start_frame = float(frame_info.split("-")[0])
                    end_frame = float(frame_info.split("-")[1].split(",")[0])
                    json_report.append(
                        {
                            "group_id": i,
                            "details": r.split("\n")[1:],
                            "start_time": start_frame / self.frame_rate,
                            "end_time": end_frame / self.frame_rate,
                        }
                    )
                except (IndexError, ValueError) as e:
                    logging.warning(f"Ошибка парсинга кадра для группы {i}: {str(e)}")
                    continue
            with open(output_file.replace(".txt", ".json"), "w", encoding="utf-8") as f:
                json.dump(json_report, f, indent=2, ensure_ascii=False)
            logging.info(f"Отчет сохранен: {len(results)} записей")
        except Exception as e:
            logging.error(f"Ошибка сохранения отчета {output_file}: {str(e)}")
