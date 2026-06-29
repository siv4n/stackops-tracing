import logging
from typing import Optional, Dict, Union, Generator, TYPE_CHECKING
from contextlib import contextmanager

from opentelemetry import propagate
from opentelemetry.context import attach, detach, Token

if TYPE_CHECKING:
    from fastapi import FastAPI

logger = logging.getLogger("stackops-tracing")


# --- AMQP Context Propagation Helpers ---

def inject_amqp_headers(headers: Optional[Dict[str, object]] = None) -> Dict[str, object]:
    """Injects current trace context and baggage into headers."""
    if headers is None:
        headers = {}
    propagate.inject(headers)
    return headers


def extract_amqp_headers(headers: Optional[Dict[str, object]]) -> Optional[Token]:
    """Extracts trace context and baggage from headers and attaches it."""
    if not headers:
        return None
    extracted_context = propagate.extract(headers)
    return attach(extracted_context)


def detach_context(token: Optional[Token]) -> None:
    """Detaches context for the token."""
    if token is not None:
        detach(token)


@contextmanager
def amqp_trace_context(headers: Optional[Dict[str, object]]) -> Generator[None, None, None]:
    """Context manager to extract and set tracing context from AMQP headers."""
    token = extract_amqp_headers(headers)
    try:
        yield
    finally:
        detach_context(token)


# --- Library Instrumentations ---

def instrument_fastapi(app: "FastAPI") -> bool:
    """Instruments a FastAPI application."""
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        FastAPIInstrumentor().instrument_app(app)
        logger.info("FastAPI application auto-instrumentation successful.")
        return True
    except ImportError as e:
        logger.warning("FastAPIInstrumentor is not installed or available: %s", e)
        return False
    except Exception as e:
        logger.error("Failed to instrument FastAPI application: %s", e)
        return False


def instrument_pymongo() -> bool:
    """Instruments PyMongo client library."""
    try:
        from opentelemetry.instrumentation.pymongo import PymongoInstrumentor
        PymongoInstrumentor().instrument()
        logger.info("PyMongo auto-instrumentation successful.")
        return True
    except ImportError as e:
        logger.warning("PymongoInstrumentor is not installed or available: %s", e)
        return False
    except Exception as e:
        logger.error("Failed to instrument PyMongo: %s", e)
        return False


def instrument_redis() -> bool:
    """Instruments Redis client library."""
    try:
        from opentelemetry.instrumentation.redis import RedisInstrumentor
        RedisInstrumentor().instrument()
        logger.info("Redis auto-instrumentation successful.")
        return True
    except ImportError as e:
        logger.warning("RedisInstrumentor is not installed or available: %s", e)
        return False
    except Exception as e:
        logger.error("Failed to instrument Redis: %s", e)
        return False


def instrument_rabbitmq() -> bool:
    """Instruments RabbitMQ client libraries (Pika/AioPika)."""
    pika_success = False
    aio_pika_success = False

    try:
        from opentelemetry.instrumentation.pika import PikaInstrumentor
        PikaInstrumentor().instrument()
        logger.info("Pika (sync RabbitMQ) auto-instrumentation successful.")
        pika_success = True
    except ImportError as e:
        logger.debug("PikaInstrumentor is not installed or available: %s", e)
    except Exception as e:
        logger.error("Failed to instrument Pika: %s", e)

    try:
        from opentelemetry.instrumentation.aio_pika import AioPikaInstrumentor
        AioPikaInstrumentor().instrument()
        logger.info("AioPika (async RabbitMQ) auto-instrumentation successful.")
        aio_pika_success = True
    except ImportError as e:
        logger.debug("AioPikaInstrumentor is not installed or available: %s", e)
    except Exception as e:
        logger.error("Failed to instrument AioPika: %s", e)

    return pika_success or aio_pika_success


def instrument_kafka() -> bool:
    """Instruments kafka-python client library."""
    try:
        from opentelemetry.instrumentation.kafka import KafkaInstrumentor
        KafkaInstrumentor().instrument()
        logger.info("Kafka auto-instrumentation successful.")
        return True
    except ImportError as e:
        logger.warning("KafkaInstrumentor is not installed or available: %s", e)
        return False
    except Exception as e:
        logger.error("Failed to instrument Kafka: %s", e)
        return False


def instrument_all(fastapi_app: Optional["FastAPI"] = None) -> None:
    """Instruments all supported libraries."""
    instrument_pymongo()
    instrument_redis()
    instrument_rabbitmq()
    instrument_kafka()
    if fastapi_app is not None:
        instrument_fastapi(fastapi_app)
