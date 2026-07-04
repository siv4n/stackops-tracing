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

Install the core package (which only depends on the core OpenTelemetry API/SDK):

```bash
pip install stackops-tracing
```

### Installation with Extras

To install specific instrumentation libraries that you need (and avoid downloading packages or conflicting versions for services you do not use):

```bash
# Install with support for Redis
pip install stackops-tracing[redis]

# Install with support for MongoDB
pip install stackops-tracing[mongo]

# Install with support for Kafka
pip install stackops-tracing[kafka]

# Install with support for RabbitMQ (Pika & AioPika)
pip install stackops-tracing[rabbit]

# Install with support for FastAPI & ASGI
pip install stackops-tracing[fastapi]

# Install with support for PostgreSQL (AsyncPG & SQLAlchemy)
pip install stackops-tracing[postgres]

# Install with ALL instrumentation packages
pip install stackops-tracing[all]
```

---

## Usage Guide

### 1. Initialization & Configuration

Configure `TracingConfigurator` at your application entry point. You can supply a `service_namespace` and `service_origin` to group your services and trace origins, which will be exported as resource attributes and can be queried inside Grafana.

```python
from stackops_tracing import TracingConfigurator, instrument_all

configurator = TracingConfigurator(
    service_name="my-service",
    service_namespace="my-namespace",  # Groups related services together in Grafana
    service_origin="my-origin",        # Identifies the origin system or project
    otlp_endpoint="http://localhost:4318",
    debug=True  # Enables console logging formatter and library logging
)
configurator.initialize()

# Instrument FastAPI, Redis, PyMongo, RabbitMQ, Kafka, AsyncPG, and SQLAlchemy
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

### 5. PostgreSQL & SQLAlchemy Instrumentation

Auto-instrumentation wraps `asyncpg` client queries and `sqlalchemy` engines.

#### asyncpg
```python
import asyncpg
from stackops_tracing import instrument_asyncpg

# Instrument asyncpg before opening connections
instrument_asyncpg()

async def run_db_query():
    conn = await asyncpg.connect(user='stackops', password='secretpassword', database='stackops_db', host='127.0.0.1')
    values = await conn.fetch("SELECT * FROM users")
    await conn.close()
```

#### SQLAlchemy
```python
from sqlalchemy import create_engine
from stackops_tracing import instrument_sqlalchemy

# Instrument SQLAlchemy before creating engines
instrument_sqlalchemy()

engine = create_engine("postgresql+psycopg2://stackops:secretpassword@localhost/stackops_db")
with engine.connect() as connection:
    result = connection.execute("SELECT * FROM users")
```

---

### 6. Decorator Usage (`@traced`)

Trace any helper function and capture its parameters and errors.

```python
from stackops_tracing import traced

@traced(name="calculate_math", attributes={"module": "finance"})
def calculate_totals(items: list, tax: float) -> float:
    return sum(items) * (1 + tax)
```

---

### 7. W3C Baggage Helpers

Baggage items carry custom values (like `tenant_id`) downstream across all services.

```python
from stackops_tracing import set_baggage_item, get_baggage_item

set_baggage_item("tenant_id", "company-xyz")
tenant_id = get_baggage_item("tenant_id", default="default")
```

---

### 8. Local Observability Stack & Collector Setup

To run a local telemetry collector stack (OTel Collector, Tempo, Prometheus, and Grafana), you can configure the following files in a directory (e.g., `local-dev/`):

#### Docker Compose Configuration (`docker-compose.yml`)
```yaml
version: '3.8'

services:
  otel-collector:
    image: otel/opentelemetry-collector-contrib:0.95.0
    command: ["--config=/etc/otel-collector-config.yaml"]
    volumes:
      - ./otel-collector-config.yaml:/etc/otel-collector-config.yaml
    ports:
      - "4317:4317" # OTLP gRPC receiver
      - "4318:4318" # OTLP HTTP receiver
      - "8889:8889" # Prometheus metrics exposure
    depends_on:
      - tempo

  tempo:
    image: grafana/tempo:2.4.0
    command: [ "-config.file=/etc/tempo.yaml" ]
    volumes:
      - ./tempo.yaml:/etc/tempo.yaml
    ports:
      - "3200:3200"   # tempo

  prometheus:
    image: prom/prometheus:v2.51.0
    volumes:
      - ./prometheus.yaml:/etc/prometheus/prometheus.yml
    ports:
      - "9090:9090"

  grafana:
    image: grafana/grafana:10.4.1
    volumes:
      - ./grafana-datasources.yaml:/etc/grafana/provisioning/datasources/datasources.yaml
    environment:
      - GF_AUTH_ANONYMOUS_ENABLED=true
      - GF_AUTH_ANONYMOUS_ORG_ROLE=Admin
    ports:
      - "3000:3000"
    depends_on:
      - prometheus
      - tempo
```

#### OTel Collector Configuration (`otel-collector-config.yaml`)
```yaml
receivers:
  otlp:
    protocols:
      grpc:
        endpoint: 0.0.0.0:4317
      http:
        endpoint: 0.0.0.0:4318

processors:
  batch:

exporters:
  otlp/tempo:
    endpoint: tempo:4317
    tls:
      insecure: true
  prometheus:
    endpoint: 0.0.0.0:8889
    namespace: otel

service:
  pipelines:
    traces:
      receivers: [otlp]
      processors: [batch]
      exporters: [otlp/tempo]
    metrics:
      receivers: [otlp]
      processors: [batch]
      exporters: [prometheus]
```

#### Tempo Configuration (`tempo.yaml`)
```yaml
stream_over_http: true
server:
  http_listen_port: 3200

distributor:
  receivers:
    otlp:
      protocols:
        grpc:
          endpoint: 0.0.0.0:4317
        http:
          endpoint: 0.0.0.0:4318

ingester:
  max_block_duration: 5m

compactor:
  ring:
    kvstore:
      store: memberlist
  config:
    max_compaction_objects: 100000
    block_retention: 24h

storage:
  trace:
    backend: local
    local:
      path: /tmp/tempo/blocks

search:
  enabled: true
```

#### Prometheus Configuration (`prometheus.yaml`)
```yaml
global:
  scrape_interval: 5s

scrape_configs:
  - job_name: 'otel-collector'
    static_configs:
      - targets: ['otel-collector:8889']
```

#### Grafana Provisioning Datasources (`grafana-datasources.yaml`)
```yaml
apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: false
  - name: Tempo
    type: tempo
    access: proxy
    url: http://tempo:3200
    isDefault: true
```

#### Querying in Grafana
Once you start this stack with `docker compose up -d`, metrics and traces will be sent to the OTel Collector.
1. Open Grafana at `http://localhost:3000`.
2. Go to **Explore** and select the **Tempo** datasource.
3. Query and filter traces using the project namespaces and origins configured in your python service:
   - `{.service.namespace = "my-namespace"}`
   - `{.service.origin = "my-origin"}`
   - `{.service.name = "my-service"}`
