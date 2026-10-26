from config import BOOTSTRAP_SERVERS, PROCESSED_TOPIC, RAW_TOPIC
from kafka import KafkaConsumer
import logging
import json

logger = logging.getLogger(__name__)

consumer = KafkaConsumer(
    RAW_TOPIC,
    bootstrap_servers=["localhost:9092"],
    group_id="my-group",
    enable_auto_commit=False,
    auto_offset_reset="latest",
    max_poll_records=50,
    fetch_min_bytes=1,
    fetch_max_wait_ms=50,
    max_poll_interval_ms=300000,
    session_timeout_ms=30000,
    heartbeat_interval_ms=3000
)

logger.info(f"Starting consumer...")
for message in consumer:
    pass