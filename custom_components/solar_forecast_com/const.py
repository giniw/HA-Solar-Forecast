DOMAIN = "solar_forecast_com"

API_URL = "https://solar-forecast.com/forecast"
API_URL_GENERATION = "https://solar-forecast.com/generation"

CONF_API_KEY = "api_key"
CONF_NAME = "identifier"
# Existing config-entry key; keep the original string for backward compatibility.
CONF_POWER_SENSOR = "Sensor For Sending Production Data"
CONF_SEND_GENERATION = "send_generation_data"


def send_generation_enabled(entry) -> bool:
    """Whether generation should be uploaded and then read back from the cloud.

    New installs always store the checkbox. Existing entries without the key
    keep the previous behaviour (fetch cloud generation, upload if a sensor
    is configured).
    """
    if CONF_SEND_GENERATION in entry.data:
        return bool(entry.data[CONF_SEND_GENERATION])
    return True
