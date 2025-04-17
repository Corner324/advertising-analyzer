import logging
import os

def setup_logging(log_file: str = "ad_quality.log"):
    logging.basicConfig(
        filename=log_file,
        level=logging.DEBUG,
        format="%(levelname)s: %(message)s",
        encoding="utf-8",
        filemode="w"
    )