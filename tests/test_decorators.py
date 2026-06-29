import asyncio
import unittest
from unittest.mock import MagicMock, patch
from stackops_tracing.decorators import traced
from stackops_tracing.config import set_baggage_item
from opentelemetry.trace import StatusCode


class TestDecorators(unittest.TestCase):
    @patch("stackops_tracing.decorators.trace.get_tracer")
    def test_sync_traced(self, mock_get_tracer):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        @traced(name="custom-sync", attributes={"env": "test"})
        def sample_func(a, b, c="default"):
            return a + b

        result = sample_func(1, 2)
        self.assertEqual(result, 3)

        # Verify span started with correct name
        mock_tracer.start_as_current_span.assert_called_once_with("custom-sync")

        # Verify span attributes set
        mock_span.set_attributes.assert_called_once_with({"env": "test"})
        mock_span.set_attribute.assert_any_call("function.param.a", "1")
        mock_span.set_attribute.assert_any_call("function.param.b", "2")
        mock_span.set_attribute.assert_any_call("function.param.c", "default")

    @patch("stackops_tracing.decorators.trace.get_tracer")
    def test_async_traced(self, mock_get_tracer):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        @traced
        async def sample_async_func(x):
            await asyncio.sleep(0.001)
            return x * 2

        result = asyncio.run(sample_async_func(10))
        self.assertEqual(result, 20)

        # Verify span started with function name
        mock_tracer.start_as_current_span.assert_called_once_with("sample_async_func")
        mock_span.set_attribute.assert_any_call("function.param.x", "10")

    @patch("stackops_tracing.decorators.trace.get_tracer")
    def test_traced_exception(self, mock_get_tracer):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        @traced
        def error_func():
            raise ValueError("Something went wrong")

        with self.assertRaises(ValueError):
            error_func()

        # Check that exception is recorded and status is set to ERROR
        mock_span.record_exception.assert_called_once()
        self.assertEqual(mock_span.record_exception.call_args[0][0].args[0], "Something went wrong")
        mock_span.set_status.assert_called_once()
        status_arg = mock_span.set_status.call_args[0][0]
        self.assertEqual(status_arg.status_code, StatusCode.ERROR)
        self.assertEqual(status_arg.description, "Something went wrong")

    @patch("stackops_tracing.decorators.trace.get_tracer")
    def test_traced_baggage_propagation(self, mock_get_tracer):
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_as_current_span.return_value.__enter__.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        # Set a baggage item
        token = set_baggage_item("request_id", "req-12345")
        try:
            @traced
            def my_func():
                pass
            
            my_func()
            
            # Verify the active baggage item was copied to span attribute
            mock_span.set_attribute.assert_any_call("baggage.request_id", "req-12345")
        finally:
            from opentelemetry.context import detach
            detach(token)
