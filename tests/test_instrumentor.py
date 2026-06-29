import unittest
from unittest.mock import MagicMock, patch
from stackops_tracing.instrumentor import (
    inject_amqp_headers,
    extract_amqp_headers,
    amqp_trace_context,
    instrument_all,
    instrument_fastapi,
    instrument_pymongo,
    instrument_redis,
    instrument_rabbitmq,
    instrument_kafka,
)
from opentelemetry import propagate
from opentelemetry.context import Token


class TestInstrumentor(unittest.TestCase):
    @patch("stackops_tracing.instrumentor.propagate.inject")
    def test_inject_amqp_headers(self, mock_inject):
        headers = {}
        inject_amqp_headers(headers)
        mock_inject.assert_called_once_with(headers)

        # Calling with None should create a dict and inject
        result = inject_amqp_headers(None)
        self.assertIsInstance(result, dict)

    @patch("stackops_tracing.instrumentor.propagate.extract")
    @patch("stackops_tracing.instrumentor.attach")
    @patch("stackops_tracing.instrumentor.detach")
    def test_extract_and_context_manager(self, mock_detach, mock_attach, mock_extract):
        mock_context = MagicMock()
        mock_extract.return_value = mock_context
        mock_token = MagicMock()
        mock_attach.return_value = mock_token

        headers = {"traceparent": "dummy-traceparent"}
        
        # Test direct extraction
        token = extract_amqp_headers(headers)
        mock_extract.assert_called_once_with(headers)
        mock_attach.assert_called_once_with(mock_context)
        self.assertEqual(token, mock_token)

        # Test context manager
        mock_extract.reset_mock()
        mock_attach.reset_mock()
        with amqp_trace_context(headers):
            pass
            
        mock_extract.assert_called_once_with(headers)
        mock_attach.assert_called_once_with(mock_context)
        mock_detach.assert_called_once_with(mock_token)

    @patch("stackops_tracing.instrumentor.logger")
    def test_resilient_imports(self, mock_logger):
        # We patch sys.modules to simulate missing dependencies, causing ImportError
        with patch.dict("sys.modules", {
            "opentelemetry.instrumentation.fastapi": None,
            "opentelemetry.instrumentation.pymongo": None,
            "opentelemetry.instrumentation.redis": None,
            "opentelemetry.instrumentation.pika": None,
            "opentelemetry.instrumentation.aio_pika": None,
            "opentelemetry.instrumentation.kafka": None
        }):
            res_fastapi = instrument_fastapi(None)
            self.assertFalse(res_fastapi)
            mock_logger.warning.assert_called_once()
            
            mock_logger.reset_mock()
            res_pymongo = instrument_pymongo()
            self.assertFalse(res_pymongo)
            mock_logger.warning.assert_called_once()

            mock_logger.reset_mock()
            res_redis = instrument_redis()
            self.assertFalse(res_redis)
            mock_logger.warning.assert_called_once()

            mock_logger.reset_mock()
            res_rmq = instrument_rabbitmq()
            self.assertFalse(res_rmq)
            self.assertTrue(mock_logger.debug.called)

            mock_logger.reset_mock()
            res_kafka = instrument_kafka()
            self.assertFalse(res_kafka)
            mock_logger.warning.assert_called_once()

    @patch("opentelemetry.instrumentation.kafka.KafkaInstrumentor")
    def test_instrument_kafka_success(self, mock_kafka_instrumentor_class):
        mock_instance = MagicMock()
        mock_kafka_instrumentor_class.return_value = mock_instance
        
        result = instrument_kafka()
        self.assertTrue(result)
        mock_instance.instrument.assert_called_once()

