# stackops-tracing

A simple, lightweight, and type-safe tracing package built on OpenTelemetry for Python 3.12+ microservices. It configures distributed tracing (OTLP over HTTP) and integrates context correlation for console logging.

---

## Features
- **Traces to Collector**: Sends trace spans to OTel Collector (`/v1/traces`) over HTTP.
- **W3C Baggage Enrichment**: Cross-service attributes automatically enrich every trace span.
- **Safe Auto-Instrumentation**: Wrappers for FastAPI, Redis, Mongo, RabbitMQ, and Kafka.
- **Debug-Only Console Logging**: Trace-correlation formatting (printing `trace_id` and `span_id`) is only enabled in debug mode.

---

## Installation

```bash
pip install -e .
```

---

## Usage Guide

### 1. Initialization & Configuration

Configure `TracingConfigurator` at your application entry point.

```python
from stackops_tracing import TracingConfigurator, instrument_all

configurator = TracingConfigurator(
    service_name="my-service",
    otlp_endpoint="http://localhost:4318",
    debug=True  # Enables console logging formatter and library logging
)
configurator.initialize()

# Instrument FastAPI, Redis, PyMongo, RabbitMQ, and Kafka
instrument_all()
```

### 2. Debug Mode Logging
By default, the library logs nothing to avoid stdout/stderr pollution. To enable trace correlation formatting and internal debug logging, pass `debug=True` to `TracingConfigurator`.

When enabled, console logs will be formatted as:
```text
2026-06-25 10:00:00,000 [INFO] [trace_id=4bf92f3577b34da6a3ce929d0e0e4736 span_id=00f067aa0ba902b7] logger_name: My log message
```

---

### 3. Kafka Instrumentation

Auto-instrumentation wraps standard `kafka-python` producers and consumers, automatically propagating trace context across services.

#### Producer Setup
```python
from kafka import KafkaProducer
from stackops_tracing import traced

producer = KafkaProducer(bootstrap_servers='localhost:9092')

@traced(name="send_kafka_message")
def publish_message():
    producer.send('order-topic', b'{"order_id": 123}')
    producer.flush()
```

#### Consumer Setup
```python
from kafka import KafkaConsumer
from stackops_tracing import traced

consumer = KafkaConsumer('order-topic', bootstrap_servers='localhost:9092')

@traced(name="process_kafka_message")
def process_message(msg):
    print(f"Processing: {msg.value}")

for message in consumer:
    process_message(message)
```

---

### 4. RabbitMQ Cross-Service Propagation

For RabbitMQ, manually inject/extract trace headers:

#### Publisher
```python
import pika
from stackops_tracing import inject_amqp_headers

headers = inject_amqp_headers()
channel.basic_publish(
    exchange='',
    routing_key='task_queue',
    body=b'Hello World',
    properties=pika.BasicProperties(headers=headers)
)
```

#### Consumer
```python
from stackops_tracing import amqp_trace_context

def on_message(ch, method, properties, body):
    with amqp_trace_context(properties.headers):
        print(f"Received: {body}")
```

---

### 5. Decorator Usage (`@traced`)

Trace any helper function and capture its parameters and errors.

```python
from stackops_tracing import traced

@traced(name="calculate_math", attributes={"module": "finance"})
def calculate_totals(items: list, tax: float) -> float:
    return sum(items) * (1 + tax)
```

---

### 6. W3C Baggage Helpers

Baggage items carry custom values (like `tenant_id`) downstream across all services.

```python
from stackops_tracing import set_baggage_item, get_baggage_item

set_baggage_item("tenant_id", "company-xyz")
tenant_id = get_baggage_item("tenant_id", default="default")
```
