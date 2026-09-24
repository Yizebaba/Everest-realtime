"""Extract the configured Everest weather thresholds from Windy forecast responses."""
import math


def _numbers(value):
    if isinstance(value, list):
        return [float(item) for item in value if isinstance(item, (int, float)) and math.isfinite(item)]
    return [float(value)] if isinstance(value, (int, float)) and math.isfinite(value) else []


def metrics(result):
    """Return peak wind, forecast precipitation and minimum temperature if exposed by Windy."""
    wind, precipitation, temperature = [], [], []
    stack = [record.get('data') for record in result.get('network_records', [])]
    while stack:
        value = stack.pop()
        if isinstance(value, dict):
            for key, item in value.items():
                name = key.lower()
                if name in ('wind', 'windspeed', 'wind_speed'):
                    wind.extend(_numbers(item))
                elif name in ('precipamount', 'precipitation', 'rain'):
                    precipitation.extend(_numbers(item))
                elif name in ('temperature', 'temperature_2m', 'temp'):
                    temperature.extend(_numbers(item))
                if isinstance(item, (dict, list)):
                    stack.append(item)
        elif isinstance(value, list):
            stack.extend(value)
    return {
        'wind_kmh': round(max(wind) * 3.6, 1) if wind else None,
        'precipitation_mm': round(sum(precipitation), 1) if precipitation else None,
        'temperature_c': round(min(item - 273.15 if item > 100 else item for item in temperature), 1) if temperature else None,
    }
