import abc
from typing import Any, Dict, List, Optional
import httpx
from app.core.config import settings
from app.core.exceptions import ServiceUnavailableException
from app.core.logging import logger
from app.schemas.location import LocationSearchCoordinate, LocationSearchItem


class BaseGeocodingProvider(abc.ABC):
    @abc.abstractmethod
    async def search_places(
        self,
        query: str,
        limit: int = 10,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[LocationSearchItem]:
        """Search for locations matching the query."""
        pass

    @abc.abstractmethod
    async def geocode_address(self, address_str: str) -> Optional[Dict[str, Any]]:
        """Geocode an address string to a GeoJSON Point or None."""
        pass

    @abc.abstractmethod
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        """Reverse geocode coordinates to structured address dictionary."""
        pass


class MockGeocodingProvider(BaseGeocodingProvider):
    """
    Development and testing geocoding provider.
    Maintains verified location data for Indore launch cluster and test locations.
    Never returns fabricated or invalid coordinates.
    """

    MOCK_DATABASE = [
        {
            "placeId": "mock-khudel-01",
            "name": "Khudel",
            "formattedAddress": "Khudel, Indore, Madhya Pradesh 453115, India",
            "locality": "Khudel",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "latitude": 22.6841,
            "longitude": 75.9782,
        },
        {
            "placeId": "mock-index-med-02",
            "name": "Index Medical College",
            "formattedAddress": "Index Medical College, Nemawar Road, Indore, Madhya Pradesh 452016, India",
            "locality": "Index Medical College",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "452016",
            "latitude": 22.7153,
            "longitude": 75.9525,
        },
        {
            "placeId": "mock-doublechowki-03",
            "name": "Doublechowki",
            "formattedAddress": "Doublechowki, Dewas-Indore Highway, Madhya Pradesh 455223, India",
            "locality": "Doublechowki",
            "city": "Dewas",
            "district": "Dewas",
            "state": "Madhya Pradesh",
            "postalCode": "455223",
            "latitude": 22.6950,
            "longitude": 76.0450,
        },
        {
            "placeId": "mock-baawliya-04",
            "name": "Baawliya",
            "formattedAddress": "Baawliya, Khudel, Indore, Madhya Pradesh 453115, India",
            "locality": "Baawliya",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "latitude": 22.7050,
            "longitude": 75.9850,
        },
        {
            "placeId": "mock-morad-05",
            "name": "Morad",
            "formattedAddress": "Morad, Nemawar Road, Indore, Madhya Pradesh 452016, India",
            "locality": "Morad",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "452016",
            "latitude": 22.7250,
            "longitude": 75.9650,
        },
        {
            "placeId": "mock-sindhi-baroda-06",
            "name": "Sindhi Baroda",
            "formattedAddress": "Sindhi Baroda, Indore, Madhya Pradesh 453115, India",
            "locality": "Sindhi Baroda",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "latitude": 22.6700,
            "longitude": 75.9900,
        },
        {
            "placeId": "mock-khudel-khurd-07",
            "name": "Khudel Khurd",
            "formattedAddress": "Khudel Khurd, Indore, Madhya Pradesh 453115, India",
            "locality": "Khudel Khurd",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "453115",
            "latitude": 22.6750,
            "longitude": 75.9820,
        },
        {
            "placeId": "mock-vijay-nagar-08",
            "name": "Vijay Nagar",
            "formattedAddress": "Vijay Nagar, Indore, Madhya Pradesh 452010, India",
            "locality": "Vijay Nagar",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "452010",
            "latitude": 22.7533,
            "longitude": 75.8937,
        },
        {
            "placeId": "mock-palasia-09",
            "name": "Old Palasia",
            "formattedAddress": "Old Palasia, Indore, Madhya Pradesh 452001, India",
            "locality": "Old Palasia",
            "city": "Indore",
            "district": "Indore",
            "state": "Madhya Pradesh",
            "postalCode": "452001",
            "latitude": 22.7244,
            "longitude": 75.8839,
        },
    ]

    async def search_places(
        self,
        query: str,
        limit: int = 10,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[LocationSearchItem]:
        q = query.strip().lower()
        results: List[LocationSearchItem] = []

        for item in self.MOCK_DATABASE:
            searchable = f"{item['name']} {item['formattedAddress']} {item['locality']} {item['postalCode']}".lower()
            if q in searchable:
                results.append(
                    LocationSearchItem(
                        placeId=item["placeId"],
                        name=item["name"],
                        formattedAddress=item["formattedAddress"],
                        locality=item["locality"],
                        city=item["city"],
                        district=item["district"],
                        state=item["state"],
                        postalCode=item["postalCode"],
                        location=LocationSearchCoordinate(
                            latitude=item["latitude"],
                            longitude=item["longitude"],
                        ),
                        isServiceable=False,  # Updated by serviceability check
                    )
                )
                if len(results) >= limit:
                    break

        return results

    async def geocode_address(self, address_str: str) -> Optional[Dict[str, Any]]:
        clean_addr = address_str.lower()
        for item in self.MOCK_DATABASE:
            if (
                item["name"].lower() in clean_addr
                or item["locality"].lower() in clean_addr
                or item["postalCode"] in clean_addr
            ):
                return {
                    "type": "Point",
                    "coordinates": [item["longitude"], item["latitude"]],
                }
        return None

    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        # Match closest within ~2km
        for item in self.MOCK_DATABASE:
            lat_diff = abs(item["latitude"] - latitude)
            lon_diff = abs(item["longitude"] - longitude)
            if lat_diff < 0.02 and lon_diff < 0.02:
                return item
        return None


class GoogleMapsGeocodingProvider(BaseGeocodingProvider):
    """Production provider using Google Places & Geocoding API."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or settings.GOOGLE_PLACES_API_KEY or settings.GOOGLE_MAPS_API_KEY
        if not self.api_key:
            raise ServiceUnavailableException(
                "Google Maps API key is not configured.",
                code="GEOCODING_PROVIDER_NOT_CONFIGURED",
            )
        self.timeout = float(settings.GEOCODING_TIMEOUT_SECONDS)

    async def search_places(
        self,
        query: str,
        limit: int = 10,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
    ) -> List[LocationSearchItem]:
        url = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
        params: Dict[str, Any] = {
            "input": query,
            "key": self.api_key,
            "components": "country:in",
        }
        if latitude is not None and longitude is not None:
            params["location"] = f"{latitude},{longitude}"
            params["radius"] = "50000"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    status = data.get("status")
                    if status in ["OVER_QUERY_LIMIT", "REQUEST_DENIED"]:
                        logger.error(f"Google Places API error: {status}")
                        raise ServiceUnavailableException(
                            "Geocoding provider quota exceeded or request denied.",
                            code="GEOCODING_PROVIDER_ERROR",
                        )

                    items: List[LocationSearchItem] = []
                    for pred in data.get("predictions", [])[:limit]:
                        items.append(
                            LocationSearchItem(
                                placeId=pred.get("place_id", ""),
                                name=pred.get("structured_formatting", {}).get("main_text", pred.get("description", "")),
                                formattedAddress=pred.get("description", ""),
                                locality=None,
                                city=None,
                                district=None,
                                state=None,
                                postalCode=None,
                                location=LocationSearchCoordinate(latitude=None, longitude=None),
                                isServiceable=False,
                            )
                        )
                    return items
                else:
                    logger.error(f"Google Maps API returned HTTP {res.status_code}")
                    raise ServiceUnavailableException("Geocoding service unavailable.", code="GEOCODING_UNAVAILABLE")
        except httpx.TimeoutException:
            logger.warning(f"Geocoding request timed out after {self.timeout}s.")
            raise ServiceUnavailableException("Geocoding request timed out.", code="GEOCODING_TIMEOUT")
        except httpx.RequestError as exc:
            logger.error(f"Geocoding request connection error: {exc}")
            raise ServiceUnavailableException("Geocoding service connection failed.", code="GEOCODING_CONNECTION_ERROR")

    async def geocode_address(self, address_str: str) -> Optional[Dict[str, Any]]:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"address": address_str, "key": self.api_key, "components": "country:in"}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    if results:
                        loc = results[0].get("geometry", {}).get("location", {})
                        lat, lng = loc.get("lat"), loc.get("lng")
                        if lat is not None and lng is not None:
                            return {"type": "Point", "coordinates": [float(lng), float(lat)]}
            return None
        except Exception as exc:
            logger.error(f"Google geocoding error: {exc}")
            return None

    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[Dict[str, Any]]:
        url = "https://maps.googleapis.com/maps/api/geocode/json"
        params = {"latlng": f"{latitude},{longitude}", "key": self.api_key}
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                res = await client.get(url, params=params)
                if res.status_code == 200:
                    data = res.json()
                    results = data.get("results", [])
                    if results:
                        return results[0]
            return None
        except Exception as exc:
            logger.error(f"Google reverse geocoding error: {exc}")
            return None


def get_geocoding_provider() -> BaseGeocodingProvider:
    provider = settings.GEOCODING_PROVIDER.lower()
    if provider == "google":
        return GoogleMapsGeocodingProvider()
    return MockGeocodingProvider()
