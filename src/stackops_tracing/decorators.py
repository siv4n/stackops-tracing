import functools
import inspect
from typing import Callable, Optional, Dict, Union, TypeVar, ParamSpec
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from stackops_tracing.config import get_all_baggage

P = ParamSpec("P")
T = TypeVar("T")


def traced(
    func: Optional[Callable[P, T]] = None,
    *,
    name: Optional[str] = None,
    tracer_name: str = "stackops-tracer",
    attributes: Optional[Dict[str, Union[str, bool, int, float]]] = None,
    record_args: bool = True,
) -> Union[Callable[P, T], Callable[[Callable[P, T]], Callable[P, T]]]:
    """Traces synchronous and asynchronous function executions."""
    if func is None:
        return lambda f: traced(
            f,
            name=name,
            tracer_name=tracer_name,
            attributes=attributes,
            record_args=record_args,
        )

    span_name = name or func.__name__

    def prepare_span(span: trace.Span, args: tuple[object, ...], kwargs: dict[str, object]) -> None:
        if attributes:
            span.set_attributes(attributes)
        for b_key, b_val in get_all_baggage().items():
            span.set_attribute(f"baggage.{b_key}", b_val)
        if record_args:
            _record_function_arguments(span, func, args, kwargs)

    if inspect.iscoroutinefunction(func):
        @functools.wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = trace.get_tracer(tracer_name)
            with tracer.start_as_current_span(span_name) as span:
                prepare_span(span, args, kwargs)
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        return async_wrapper
    else:
        @functools.wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            tracer = trace.get_tracer(tracer_name)
            with tracer.start_as_current_span(span_name) as span:
                prepare_span(span, args, kwargs)
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    span.record_exception(e)
                    span.set_status(Status(StatusCode.ERROR, str(e)))
                    raise
        return sync_wrapper


def _record_function_arguments(
    span: trace.Span,
    func: Callable[..., object],
    args: tuple[object, ...],
    kwargs: dict[str, object]
) -> None:
    """Safely extracts and records function arguments onto the span."""
    try:
        sig = inspect.signature(func)
        bound_args = sig.bind_partial(*args, **kwargs)
        bound_args.apply_defaults()
        
        for arg_name, arg_val in bound_args.arguments.items():
            if arg_name in ("self", "cls"):
                continue

            if isinstance(arg_val, (str, int, float, bool)) or arg_val is None:
                span.set_attribute(f"function.param.{arg_name}", str(arg_val))
            elif isinstance(arg_val, (list, tuple, dict, set)):
                val_str = str(arg_val)
                if len(val_str) > 256:
                    val_str = val_str[:253] + "..."
                span.set_attribute(f"function.param.{arg_name}", val_str)
    except Exception:
        pass
