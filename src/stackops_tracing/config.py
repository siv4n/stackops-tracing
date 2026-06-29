import logging
from typing import Optional, Dict, Union
from opentelemetry import trace, baggage
from opentelemetry.context import attach, get_current, Token, Context
from opentelemetry.trace import Span
from opentelemetry.sdk.trace import TracerProvider, SpanProcessor
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.resources import Resource
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.propagate import set_global_textmap
from opentelemetry.propagators.composite import CompositePropagator
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from opentelemetry.baggage.propagation import W3CBaggagePropagator

logger = logging.getLogger("stackops-tracing")
logger.addHandler(logging.NullHandler())
logger.setLevel(logging.WARNING)


class BaggageSpanProcessor(SpanProcessor):
    """Injects active W3C baggage into all started spans."""

    def on_start(self, span: Span, parent_context: Optional[Context] = None) -> None:
        active_baggage = baggage.get_all(context=parent_context)
        for key, val in active_baggage.items():
            span.set_attribute(f"baggage.{key}", str(val))

    def on_end(self, span: Span) -> None:
        pass


class TracingFormatter(logging.Formatter):
    """Formats log records to include active trace_id and span_id."""

    def format(self, record: logging.LogRecord) -> str:
        current_span = trace.get_current_span()
        if current_span and current_span.get_span_context().is_valid:
            context = current_span.get_span_context()
            setattr(record, "trace_id", trace.format_trace_id(context.trace_id))
            setattr(record, "span_id", trace.format_span_id(context.span_id))
        else:
            setattr(record, "trace_id", "0" * 32)
            setattr(record, "span_id", "0" * 16)
        return super().format(record)


class TracingConfigurator:
    """Configures OpenTelemetry tracing and correlation formatter."""

    def __init__(
        self,
        service_name: str,
        otlp_endpoint: str = "http://localhost:4318",
        custom_resource_attrs: Optional[Dict[str, str]] = None,
        debug: bool = False,
    ) -> None:
        self.service_name = service_name
        self.otlp_endpoint = otlp_endpoint
        self.debug = debug

        if self.debug:
            logger.setLevel(logging.DEBUG)
        else:
            logger.setLevel(logging.WARNING)

        resource_attributes = {
            "service.name": self.service_name,
        }

        if custom_resource_attrs:
            resource_attributes.update(custom_resource_attrs)

        self.resource = Resource.create(resource_attributes)
        self.tracer_provider: Optional[TracerProvider] = None
        self.console_handler: Optional[logging.StreamHandler] = None

    def initialize(self, enable_tracing: bool = True) -> None:
        """Sets up global propagators, tracer provider, and logging handler."""
        set_global_textmap(
            CompositePropagator(
                [
                    TraceContextTextMapPropagator(),
                    W3CBaggagePropagator(),
                ]
            )
        )

        if enable_tracing:
            self._setup_tracer()

        if self.debug:
            self._setup_console_logging()

    def _setup_tracer(self) -> None:
        """Sets up TracerProvider and OTLP span exporter."""
        self.tracer_provider = TracerProvider(resource=self.resource)
        self.tracer_provider.add_span_processor(BaggageSpanProcessor())

        trace_url = f"{self.otlp_endpoint.rstrip('/')}/v1/traces"
        span_exporter = OTLPSpanExporter(endpoint=trace_url)
        span_processor = BatchSpanProcessor(span_exporter)
        self.tracer_provider.add_span_processor(span_processor)

        trace.set_tracer_provider(self.tracer_provider)
        logger.info("OpenTelemetry Tracer successfully initialized. Exporter endpoint: %s", trace_url)

    def _setup_console_logging(self) -> None:
        """Registers a root stream handler with TracingFormatter."""
        root_logger = logging.getLogger()
        for handler in root_logger.handlers:
            if isinstance(handler, logging.StreamHandler) and isinstance(handler.formatter, TracingFormatter):
                return

        self.console_handler = logging.StreamHandler()
        log_format = "%(asctime)s [%(levelname)s] [trace_id=%(trace_id)s span_id=%(span_id)s] %(name)s: %(message)s"
        formatter = TracingFormatter(log_format)
        self.console_handler.setFormatter(formatter)

        root_logger.addHandler(self.console_handler)
        logger.info("Console log tracing correlation enabled.")

    def shutdown(self) -> None:
        """Shuts down TracerProvider and detaches stream handler."""
        if self.tracer_provider:
            try:
                self.tracer_provider.shutdown()
                logger.info("OpenTelemetry Tracer shut down successfully.")
            except Exception as e:
                logger.error("Error shutting down TracerProvider: %s", e)

        if self.console_handler:
            try:
                root_logger = logging.getLogger()
                root_logger.removeHandler(self.console_handler)
            except Exception as e:
                logger.error("Error removing console logging handler: %s", e)


# --- Baggage Helpers ---

def set_baggage_item(key: str, value: str) -> Token:
    """Sets a baggage item in the current context."""
    current_context = get_current()
    new_context = baggage.set_baggage(key, value, context=current_context)
    return attach(new_context)


def get_baggage_item(key: str, default: Optional[str] = None) -> Optional[str]:
    """Retrieves a baggage item value from the current context."""
    val = baggage.get_baggage(key)
    if val is None:
        return default
    return str(val)


def get_all_baggage() -> Dict[str, str]:
    """Retrieves all baggage items from the current context."""
    return {str(k): str(v) for k, v in baggage.get_all().items()}
