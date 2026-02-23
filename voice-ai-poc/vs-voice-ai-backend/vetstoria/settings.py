from pydantic_settings import BaseSettings

class APISettings(BaseSettings):
    """
    Pydantic model to load API-related configuration from environment variables.
    """
    base_url: str
    auth_url: str
    partner_key: str
    site_hash: str
    secret: str
    site_id: str
    booking_hash: str
