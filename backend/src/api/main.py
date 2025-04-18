import logging
import uuid
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
    handlers=[logging.StreamHandler(), logging.FileHandler("/app/logs/api.log")],
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

# Создаем директории
for directory in [VIDEO_DIR, PREDICTIONS_DIR, REPORTS_DIR, DEBUG_DIR, LOG_DIR]:
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


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    logger.info(f"Получен запрос на загрузку файла: {file.filename}")

    # Сохраняем видео
    video_id = str(uuid.uuid4())
    video_path = VIDEO_DIR / f"{video_id}.mp4"
    filename = file.filename
    logger.info(f"Сохранение видео в: {video_path}, имя файла: {filename}")

    try:
        with open(video_path, "wb") as f:
            content = await file.read()
            f.write(content)
        logger.info(f"Видео сохранено: {video_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении видео {video_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения видео: {str(e)}")

    # Запускаем детекцию
    predictions_path = PREDICTIONS_DIR / f"{video_id}_ predictions.json"
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

    # Сохраняем отчет
    report_path = REPORTS_DIR / f"{video_id}_report.txt"
    logger.info(f"Сохранение отчета в: {report_path}")
    try:
        analyzer.save_report(results, str(report_path))
        logger.info(f"Отчет сохранен: {report_path}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении отчета {report_path}: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка сохранения отчета: {str(e)}")

    logger.info(f"Запрос успешно обработан, отчет: {report_path}")
    return {"report_path": str(report_path)}


@app.get("/report/{report_id}")
async def get_report(report_id: str):
    report_path = REPORTS_DIR / f"{report_id}_report.txt"
    logger.info(f"Запрос отчета: {report_path}")

    if not report_path.exists():
        logger.error(f"Отчет не найден: {report_path}")
        raise HTTPException(status_code=404, detail="Отчет не найден")

    logger.info(f"Отправка отчета: {report_path}")
    return FileResponse(report_path)


@app.get("/health")
async def health_check():
    logger.info("Проверка состояния сервера")
    return {"status": "healthy"}
