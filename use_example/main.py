from use_example.config import BOOTSTRAP_SERVERS, PROCESSED_TOPIC, RAW_TOPIC, CONTRACT_PATH
from use_example.validate import validate_order
from use_example.adapt import adapt_order
from kafka import KafkaConsumer
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

logger.info(f"Starting consumer...")
contract = read_contract()
for message in consumer:
    data = message.value
    diagnosis = validate_order(data, contract["schema"])
    if not diagnosis["valid"]:
        continue
    data = adapt_order(data, diagnosis)
