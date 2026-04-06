"""
Configuración de logging estructurado para el Barça Calendar Bot.

En producción (variable de entorno JSON_LOGS=true) los logs se emiten en formato JSON,
facilitando su ingestión por sistemas como ELK o Cloud Logging.
En desarrollo se usa un formato legible por humanos.
"""

import json
import logging
import sys
from typing import Any

# Constantes
JSON_LOGS_ENV_VAR = "JSON_LOGS"


class JsonFormatter(logging.Formatter):
    """Formateador que produce logs en formato JSON."""

    def format(self, record: logging.LogRecord) -> str:
        log_object = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info:
            log_object["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "props") and isinstance(record.props, dict):
            log_object.update(record.props)
        return json.dumps(log_object, ensure_ascii=False)


def setup_logging(
    level: str = "INFO",
    json_logs: bool = False,
    logger_name: str = "barca_bot",
) -> logging.Logger:
    """
    Configura el logging global y devuelve un logger listo para usar.

    Args:
        level: Nivel de logging (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_logs: Si es True, usa formato JSON; si es False, formato legible.
        logger_name: Nombre del logger principal.

    Returns:
        Logger configurado.
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, level.upper()))

    # Evitar handlers duplicados
    if logger.handlers:
        return logger

    handler = logging.StreamHandler(sys.stdout)
    if json_logs:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # También configuramos el logging de las bibliotecas de Google y requests
    # para que no sean demasiado verbosas por defecto.
    logging.getLogger("googleapiclient").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """
    Obtiene un logger con la configuración actual.

    Si el logging aún no ha sido configurado, lo configura automáticamente
    leyendo la variable de entorno JSON_LOGS.

    Args:
        name: Nombre del logger (si es None, se usa el logger raíz 'barca_bot').

    Returns:
        Logger listo para usar.
    """
    root_logger = logging.getLogger("barca_bot")
    if not root_logger.handlers:
        json_logs = os.environ.get(JSON_LOGS_ENV_VAR, "").strip().lower() == "true"
        setup_logging(json_logs=json_logs)
    if name is None:
        return root_logger
    return logging.getLogger(name)


# Importación segura de os para uso en la función
import os  # noqa: E402

# Logger por defecto (se configurará en el primer uso)
logger = get_logger()


# Funciones de conveniencia para logging con propiedades adicionales
def log_with_props(
    level: str,
    message: str,
    props: dict[str, Any],
    logger_name: str = "barca_bot",
) -> None:
    """
    Emite un log con propiedades adicionales (estructuradas).

    Args:
        level: Nivel de logging.
        message: Mensaje principal.
        props: Diccionario con propiedades adicionales.
        logger_name: Nombre del logger.
    """
    log = get_logger(logger_name)
    log_record = log.makeRecord(
        log.name,
        getattr(logging, level.upper()),
        "(unknown)",
        0,
        message,
        None,
        None,
        None,
    )
    log_record.props = props  # type: ignore
    log.handle(log_record)
