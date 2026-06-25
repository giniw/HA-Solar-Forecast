"this is the sensor updated file"
async def async_update(self):
        """Fetch fresh forecast metrics directly from your web server API."""
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "HomeAssistantIntegration/1.0"
        }
        
        async with aiohttp.ClientSession() as session:
            try:
                url = "https://solar-forecast.com/api-view.html"
                async with session.get(url, headers=headers, timeout=15) as response:
                    if response.status == 200:
                        json_payload = await response.json()
                        
                        # Maps the JSON keys from your server payload
                        self._state = json_payload.get("total_predicted_kwh")
                        self._extra_attributes = {
                            "hourly_breakdown": json_payload.get("hourly_predictions")
                        }
                    else:
                        _LOGGER.error("Failed to fetch data from Solar-Forecast: HTTP %s", response.status)
            except Exception as err:
                _LOGGER.error("Error communicating with Solar-Forecast server: %s", err)
