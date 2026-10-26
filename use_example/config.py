from dotenv import load_dotenv
import logging
import os

load_dotenv()
logging = logging.getLogger(__name__)

def get_env(name: str) -> str:
    """Get environment variable value."""
    try:
        value = os.getenv(name)
        if not value:
            logging.warning(f"Environment variable {name} is not set.")
            raise ValueError
        return value

    except Exception as e:
        logging.error(f"Error getting environment variable {name}: {e}")
        return None

BOOTSTRAP_SERVERS = get_env("BOOTSTRAP_SERVERS")
API_KEY = get_env("API_KEY")
RAW_TOPIC = get_env("RAW_TOPIC")
PROCESSED_TOPIC = get_env("PROCESSED_TOPIC")


ENDPOINT = get_env("ENDPOINT")