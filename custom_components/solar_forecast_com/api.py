from aiohttp import ClientError

from homeassistant.helpers.aiohttp_client import async_get_clientsession


class AuthenticationError(Exception):
    """Raised when the API key is invalid."""


async def validate_api_key(hass, api_url, api_key):
    """Validate the supplied API key."""

    session = async_get_clientsession(hass)

    params = {"api_key": api_key}

    try:
        async with session.get(api_url, params=params) as response:

            if response.status == 200:
                return True

            if response.status in (401, 403):
                raise AuthenticationError()

            raise Exception(f"HTTP {response.status}")

    except ClientError as err:
        raise Exception(err) from err
