from use_example.config import BOOTSTRAP_SERVERS, PROCESSED_TOPIC, RAW_TOPIC, CONTRACT_PATH
from use_example.validate import validate_order
from kafka import KafkaConsumer, KafkaProducer
from use_example.adapt import adapt_order
from typing import Any
from pathlib import Path
import logging
import json
import yaml

logger = logging.getLogger(__name__)

def read_contract(contract_path: str = CONTRACT_PATH) -> dict[str, Any]:
    """Read the data contract from a YAML file."""
    try:
        with open(Path(__file__).parent / contract_path, "r", encoding="utf-8") as file:
            contract = yaml.safe_load(file)
            logger.info("Contract file read successfully.")
        return contract
    except Exception as e:
        logger.error(f"Error reading contract file {contract_path}: {e}")
        raise RuntimeError(f"Failed to read contract file: {e}")

consumer = KafkaConsumer(
    RAW_TOPIC,
    bootstrap_servers=BOOTSTRAP_SERVERS,
    group_id="order_validation_group",
    value_deserializer=lambda m: json.loads(m.decode("utf-8")),
    enable_auto_commit=False,
    auto_offset_reset="latest",
    fetch_max_wait_ms=50,
    session_timeout_ms=30000,
    heartbeat_interval_ms=3000
)

processed_producer = KafkaProducer(
    bootstrap_servers=BOOTSTRAP_SERVERS,
    value_serializer=lambda m: json.dumps(m).encode("utf-8"),
    key_serializer=lambda k: str(k).encode("utf-8") if k is not None else None,
    acks="all",
    linger_ms=10,
    enable_idempotence=True
)

logger.info(f"Starting consumer...")
contract = read_contract()
for message in consumer:
    data = message.value
    diagnosis = validate_order(data, contract["schema"])

    if not diagnosis["valid"]:
        consumer.commit()
        continue
    
    data = adapt_order(data, diagnosis)
    processed_producer.send(PROCESSED_TOPIC, key=data.get("order_id"), value=data).get(timeout=10)
    consumer.commit()
