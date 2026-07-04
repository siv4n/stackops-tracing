import unittest
from unittest.mock import MagicMock, patch
from stackops_tracing.config import TracingConfigurator, set_baggage_item, get_baggage_item, get_all_baggage
from opentelemetry import baggage


class TestConfig(unittest.TestCase):
    @patch("stackops_tracing.config.TracerProvider")
    @patch("stackops_tracing.config.OTLPSpanExporter")
    @patch("stackops_tracing.config.set_global_textmap")
    def test_initialize(self, mock_set_global_textmap, mock_span_exporter, mock_tracer_provider):
        configurator = TracingConfigurator(
            service_name="test-service",
            otlp_endpoint="http://otel-collector:4318",
            custom_resource_attrs={"custom.key": "custom.value"},
            debug=True
        )
        
        configurator.initialize(enable_tracing=True)
        
        # Verify textmap propagator is set
        mock_set_global_textmap.assert_called_once()
        
        # Verify TracerProvider created with correct resource
        mock_tracer_provider.assert_called_once()
        resource = mock_tracer_provider.call_args[1].get("resource")
        self.assertIsNotNone(resource)
        self.assertEqual(resource.attributes["service.name"], "test-service")
        self.assertEqual(resource.attributes["custom.key"], "custom.value")
        
        # Verify console logging handler is registered
        import logging
        from stackops_tracing.config import TracingFormatter
        root_logger = logging.getLogger()
        has_handler = any(
            isinstance(h, logging.StreamHandler) and isinstance(h.formatter, TracingFormatter)
            for h in root_logger.handlers
        )
        self.assertTrue(has_handler)
        
        # Verify shutdown calls shutdown on provider and detaches handler
        configurator.shutdown()
        configurator.tracer_provider.shutdown.assert_called_once()
        
        has_handler_after = any(
            isinstance(h, logging.StreamHandler) and isinstance(h.formatter, TracingFormatter)
            for h in root_logger.handlers
        )
        self.assertFalse(has_handler_after)

    def test_baggage_helpers(self):
        # Test setting and getting baggage
        token = set_baggage_item("user_id", "98765")
        try:
            self.assertEqual(get_baggage_item("user_id"), "98765")
            self.assertEqual(get_baggage_item("nonexistent", "default"), "default")
            
            all_baggage = get_all_baggage()
            self.assertIn("user_id", all_baggage)
            self.assertEqual(all_baggage["user_id"], "98765")
        finally:
            from opentelemetry.context import detach
            detach(token)

    def test_baggage_span_processor(self):
        from stackops_tracing.config import BaggageSpanProcessor
        
        mock_span = MagicMock()
        processor = BaggageSpanProcessor()
        
        token = set_baggage_item("tenant_id", "company-123")
        try:
            processor.on_start(mock_span)
            mock_span.set_attribute.assert_called_once_with("baggage.tenant_id", "company-123")
        finally:
            from opentelemetry.context import detach
            detach(token)

    def test_debug_mode(self):
        import logging
        from stackops_tracing.config import logger as config_logger
        
        # Test default is WARNING (debug=False)
        configurator_default = TracingConfigurator(service_name="test-default")
        self.assertEqual(config_logger.level, logging.WARNING)

        # Test debug=True sets level to DEBUG
        configurator_debug = TracingConfigurator(service_name="test-debug", debug=True)
        self.assertEqual(config_logger.level, logging.DEBUG)

    def test_resource_attributes(self):
        configurator = TracingConfigurator(
            service_name="my-service",
            service_namespace="my-namespace",
            service_origin="my-origin",
        )
        self.assertEqual(configurator.resource.attributes["service.name"], "my-service")
        self.assertEqual(configurator.resource.attributes["service.namespace"], "my-namespace")
        self.assertEqual(configurator.resource.attributes["service.origin"], "my-origin")
        self.assertEqual(configurator.resource.attributes["project.origin"], "my-origin")

