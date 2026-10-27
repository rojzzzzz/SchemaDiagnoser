from use_example.config import BOOTSTRAP_SERVERS, ENDPOINT, RAW_TOPIC
from kafka import KafkaProducer
import requests
import logging
import json
import time

logger = logging.getLogger(__name__)

producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    value_serializer=lambda v: json.dumps(v).encode("utf-8"),
    key_serializer=lambda k: json.dumps(k).encode("utf-8"),
    enable_idempotence=True,
    acks="all",
    linger_ms=5
)

def request_data(session: requests.Session):
    """Request data from the mock API"""

    try:
        response = session.get(ENDPOINT, timeout=5)
        response.raise_for_status()
        return response.json()

    except requests.HTTPStatusError as e:

        if e.response.status_code == 404:
            logger.error(f"Endpoint not found: {ENDPOINT}")
        logger.error(f"HTTP error occurred: {e}")
        raise RuntimeError
    except Exception as e:
        logger.error(f"Error requesting data from {ENDPOINT}: {e}")
        raise RuntimeError

def make_data_highway():
    """Request data from the mock API and send it to Kafka"""
    with requests.Session() as session:
        try:
            for _ in range(10000):
                    response = request_data(session)
                    # Publish the batch without incrementing an unused, undefined counter.
                    for order in response['data']:
                        producer.send(RAW_TOPIC, key=order['order_id'], value=order)

                    time.sleep(2)

        except Exception as e:
            logger.error(f"An error occurred while sending data to Kafka: {e}")

        finally:
            producer.flush()

