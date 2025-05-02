import logging
import uuid
import hashlib
from pathlib import Path
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from src.analyzer.ad_analyzer import AdQualityAnalyzer
from src.detector.yolo_detector import YoloDetector

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("/app/logs/ad_quality.log")],
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Ad Quality System")

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8080", "http://frontend:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Пути для временных файлов
VIDEO_DIR = Path("/app/videos")
PREDICTIONS_DIR = Path("/app/predictions")
REPORTS_DIR = Path("/app/reports")
MODEL_PATH = Path("/app/src/detector/models/best.pt")
DEBUG_DIR = Path("/app/debug_frames")
LOG_DIR = Path("/app/logs")
CACHE_DIR = Path("/app/cache")

# Создаем директории
for directory in [VIDEO_DIR, PREDICTIONS_DIR, REPORTS_DIR, DEBUG_DIR, LOG_DIR, CACHE_DIR]:
    try:
        directory.mkdir(exist_ok=True)
        logger.info(f"Создана директория: {directory}")
    except Exception as e:
        logger.error(f"Ошибка при создании директории {directory}: {e}")
        raise

# Проверка существования модели
if not MODEL_PATH.exists():
    logger.error(f"Модель не найдена по пути: {MODEL_PATH}")
    raise FileNotFoundError(f"Модель не найдена: {MODEL_PATH}")

# Инициализация моделей
try:
    logger.info("Инициализация YoloDetector...")
    detector = YoloDetector(model_path=str(MODEL_PATH), output_dir=str(DEBUG_DIR))
    logger.info("YoloDetector инициализирован")
    logger.info("Инициализация AdQualityAnalyzer...")
    analyzer = AdQualityAnalyzer(debug_dir=str(DEBUG_DIR))
    logger.info("AdQualityAnalyzer инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации моделей: {e}")
    raise

def calculate_md5(content: bytes) -> str:
    """Вычисляет MD5-хэш содержимого файла."""
    return hashlib.md5(content).hexdigest()

@app.post("/api/upload")
async def upload_video(file: UploadFile = File(...)):
    logger.info(f"Получен запрос на загрузку файла: {file.filename}")

    # Читаем содержимое файла и вычисляем MD5
    content = await file.read()
    video_hash = calculate_md5(content)
    logger.info(f"Вычислен MD5-хэш видео: {video_hash}")

    # Проверяем кэш
    cached_report_path = REPORTS_DIR / f"{video_hash}_report.txt"
    cached_predictions_path = PREDICTIONS_DIR / f"{video_hash}_predictions.json"
    if cached_report_path.exists() and cached_predictions_path.exists():
        logger.info(f"Найден кэшированный отчёт: {cached_report_path}")
        return {"report_path": str(cached_report_path), "video_id": video_hash}

    # Сохраняем видео
    video_id = video_hash
    video_path = VIDEO_DIR / f"{video_id}.mp4"
    filename = file.filename
    logger.info(f"Сохранение видео в: {video_path}, имя файла: {filename}")

    try:
        with open(video_path, "wb") as f:
            f.write(content)
        logger.info(f"Видео сохранено: {video_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении видео {video_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения видео: {str(e)}")

    # Запускаем детекцию
    predictions_path = PREDICTIONS_DIR / f"{video_id}_predictions.json"
    logger.info(f"Запуск детекции, предсказания будут сохранены в: {predictions_path}")

    try:
        if not detector.predict_video(str(video_path), str(predictions_path)):
            logger.error(f"Детекция не удалась для видео: {video_path}")
            raise HTTPException(status_code=500, detail="Ошибка обработки видео")
        logger.info(f"Детекция завершена, предсказания сохранены: {predictions_path}")
    except Exception as e:
        logger.error(f"Ошибка при детекции видео {video_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка детекции: {str(e)}")

    # Запускаем анализ
    logger.info(f"Запуск анализа видео: {video_path}")
    try:
        results = analyzer.process_video(str(video_path), str(predictions_path), filename)
        if not results:
            logger.error(f"Анализ не вернул результатов для видео: {video_path}")
            raise HTTPException(status_code=500, detail="Ошибка анализа видео")
        logger.info(f"Анализ завершен для видео: {video_path}")
    except Exception as e:
        logger.error(f"Ошибка при анализе видео {video_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")

    # Сохраняем отчёт
    report_path = REPORTS_DIR / f"{video_id}_report.txt"
    logger.info(f"Сохранение отчёта в: {report_path}")
    try:
        analyzer.save_report(results, str(report_path))
        logger.info(f"Отчёт сохранён: {report_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении отчёта {report_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения отчёта: {str(e)}")

    logger.info(f"Запрос успешно обработан, отчёт: {report_path}")
    return {"report_path": str(report_path), "video_id": video_hash}

@app.get("/api/report/{report_id}")
async def get_report(report_id: str):
    report_path = REPORTS_DIR / f"{report_id}_report.txt"
    logger.info(f"Запрос отчёта: {report_path}")

    if not report_path.exists():
        logger.error(f"Отчёт не найден: {report_path}")
        raise HTTPException(status_code=404, detail="Отчёт не найден")

    logger.info(f"Отправка отчёта: {report_path}")
    return FileResponse(report_path)

@app.get("/api/health")
async def health_check():
    logger.info("Проверка состояния сервера")
    return {"status": "healthy"}

@app.delete("/api/clear-cache")
async def clear_cache():
    """Очищает кэш (для отладки)."""
    logger.info("Запрос на очистку кэша")
    try:
        for file in CACHE_DIR.glob("*"):
            file.unlink()
        for file in PREDICTIONS_DIR.glob("*_predictions.json"):
            file.unlink()
        for file in REPORTS_DIR.glob("*_report.txt"):
            file.unlink()
        for file in VIDEO_DIR.glob("*.mp4"):
            file.unlink()
        logger.info("Кэш успешно очищён")
        return {"status": "cache cleared"}
    except Exception as e:
        logger.error(f"Ошибка при очистке кэша: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка очистки кэша: {str(e)}")

@app.get("/api/logs")
async def get_logs(video_id: str = None):
    """Возвращает последние 50 строк из файла логов, связанных с video_id."""
    log_file = Path("/app/logs/ad_quality.log")
    logger.info(f"Запрос логов для video_id: {video_id or 'все'}")
    try:
        if not log_file.exists():
            logger.error(f"Файл логов не найден: {log_file}")
            return {"logs": []}
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            if video_id:
                # Фильтруем логи по video_id (MD5-хэш)
                filtered_lines = [line.strip() for line in lines if video_id in line]
                return {"logs": filtered_lines[-50:]}
            return {"logs": [line.strip() for line in lines[-50:]]}
    except Exception as e:
        logger.error(f"Ошибка чтения логов: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка чтения логов: {str(e)}")