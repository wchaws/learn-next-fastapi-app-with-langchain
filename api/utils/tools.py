import random
from typing import Annotated
from langchain.tools import tool
import requests


@tool
def get_current_weather2(
    location: Annotated[str, "The city and state, e.g. San Francisco, CA"],
    unit: Annotated[str, "The unit of temperature"] = "fahrenheit",
):
    """Get the current weather in a given location"""
    if unit == "celsius":
        temperature = random.randint(-34, 43)
    else:
        temperature = random.randint(-30, 110)

    return {
        "temperature": temperature,
        "unit": unit,
        "location": location,
    }


@tool
def get_current_weather(
    latitude: Annotated[float, "The latitude of the location"],
    longitude: Annotated[float, "The longitude of the location"],
):
    """Get the current weather in a given location latitude and longitude"""

    res = requests.get(
        f"https://api.open-meteo.com/v1/forecast?latitude={latitude}&longitude={longitude}&current=temperature_2m&timezone=auto"
    )

    return res.json()


@tool
def add(a: int, b: int) -> int:
    """Adds a and b."""
    return a + b


@tool
def multiply(a: int, b: int) -> int:
    """Multiplies a and b."""
    return a * b
