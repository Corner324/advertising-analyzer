import logging


def setup_logging(log_file: str = "ad_quality.log", level: int = logging.INFO):
    """
    Настраивает логирование в файл и консоль с указанным уровнем.

    Args:
        log_file (str): Путь к файлу логов. По умолчанию "ad_quality.log".
        level (int): Уровень логирования (например, logging.INFO). По умолчанию logging.INFO.
    """
    # Очищаем существующие обработчики, чтобы избежать дублирования
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    # Создаём форматтер
    formatter = logging.Formatter("%(asctime)s [%(levelname)s]: %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # Настраиваем обработчик для файла
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.setLevel(level)

    # Настраиваем обработчик для консоли
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(level)

    # Настраиваем корневой логгер
    logging.basicConfig(level=level, handlers=[file_handler, console_handler])

    logging.info(f"Логирование настроено: файл={log_file}, уровень={logging.getLevelName(level)}")
