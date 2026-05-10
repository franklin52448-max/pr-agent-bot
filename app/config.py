from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', extra='ignore')

    app_name: str = 'Zero-human PR agent'
    admin_email: str | None = None

    x402_chain_id: int = 8453
    x402_rpc_url: str | None = None
    x402_treasury_address: str = '0x0000000000000000000000000000000000000000'
    x402_usdc_contract: str = '0x0000000000000000000000000000000000000000'
    x402_min_amount_usdc: float = 0.5
    x402_required_confirmations: int = 1
    x402_price_usdc: float = 0.5

    journalist_catalog_size: int = 2200
    default_send_window_start_hour: int = 9
    default_send_window_end_hour: int = 17
    default_send_window_timezone: str = 'UTC'


settings = Settings()
