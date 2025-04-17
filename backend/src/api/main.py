import uuid
from pathlib import Path

from src.analyzer.ad_analyzer import AdQualityAnalyzer
from src.detector.yolo_detector import YoloDetector
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

app = FastAPI(title="Ad Quality System")

# Пути для временных файлов
VIDEO_DIR = Path("/app/videos")
PREDICTIONS_DIR = Path("/app/predictions")
REPORTS_DIR = Path("/app/reports")
MODEL_PATH = Path("/app/src/detector/models/best.pt")
DEBUG_DIR = Path("/app/debug_frames")

# Создаем директории
for directory in [VIDEO_DIR, PREDICTIONS_DIR, REPORTS_DIR, DEBUG_DIR]:
    directory.mkdir(exist_ok=True)

# Инициализация моделей
detector = YoloDetector(model_path=str(MODEL_PATH), output_dir=str(DEBUG_DIR))
analyzer = AdQualityAnalyzer(debug_dir=str(DEBUG_DIR))


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    # Сохраняем видео
    video_id = str(uuid.uuid4())
    video_path = VIDEO_DIR / f"{video_id}.mp4"
    with open(video_path, "wb") as f:
        f.write(await file.read())

    # Запускаем детекцию
    predictions_path = PREDICTIONS_DIR / f"{video_id}_predictions.json"
    if not detector.predict_video(str(video_path), str(predictions_path)):
        raise HTTPException(status_code=500, detail="Ошибка обработки видео")

    # Запускаем анализ
    results = analyzer.process_video(str(video_path), str(predictions_path))
    if not results:
        raise HTTPException(status_code=500, detail="Ошибка анализа видео")

    # Сохраняем отчет
    report_path = REPORTS_DIR / f"{video_id}_report.txt"
    analyzer.save_report(results, str(report_path))

    return {"report_path": str(report_path)}


@app.get("/report/{report_id}")
async def get_report(report_id: str):
    report_path = REPORTS_DIR / f"{report_id}_report.txt"
    if not report_path.exists():
        raise HTTPException(status_code=404, detail="Отчет не найден")
    return FileResponse(report_path)
