"""
Application configuration module.

Provides the :class:`Settings` model that reads configuration values from
environment variables (and an optional ``.env`` file) and the :func:`get_settings`
helper that returns a cached singleton instance.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Uses *pydantic-settings* to parse and validate environment variables
    (or entries in a ``.env`` file).  Field aliases correspond to the
    environment variable names.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = Field(default="hosting-api", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")
    database_url: str = Field(alias="DATABASE_URL")
    session_secret: str = Field(alias="SESSION_SECRET")

    backend_url: str = Field(default="http://localhost:8000", alias="BACKEND_URL")

    keycloak_server_url: str = Field(alias="KEYCLOAK_SERVER_URL")
    keycloak_realm: str = Field(alias="KEYCLOAK_REALM")
    keycloak_client_id: str = Field(alias="KEYCLOAK_CLIENT_ID")
    keycloak_client_secret: str | None = Field(default=None, alias="KEYCLOAK_CLIENT_SECRET")
    keycloak_redirect_uri: str | None = Field(default=None, alias="KEYCLOAK_REDIRECT_URI")
    keycloak_verify_tls: bool = Field(default=True, alias="KEYCLOAK_VERIFY_TLS")
    keycloak_timeout_seconds: int = Field(default=10, alias="KEYCLOAK_TIMEOUT_SECONDS")
    keycloak_http_retries: int = Field(default=2, alias="KEYCLOAK_HTTP_RETRIES")
    keycloak_admin_username: str | None = Field(default=None, alias="KEYCLOAK_ADMIN_USERNAME")
    keycloak_admin_password: str | None = Field(default=None, alias="KEYCLOAK_ADMIN_PASSWORD")

    auth_groups_claim: str = Field(default="groups", alias="AUTH_GROUPS_CLAIM")
    auth_attributes_namespace: str = Field(default="attributes", alias="AUTH_ATTRIBUTES_NAMESPACE")
    auth_user_id_claim: str = Field(default="sub", alias="AUTH_USER_ID_CLAIM")
    auth_cotise_end_claim: str = Field(default="cotise_end", alias="AUTH_COTISE_END_CLAIM")
    auth_user_groups: str = Field(default="", alias="AUTH_USER_GROUPS")
    auth_admin_groups: str = Field(default="admin", alias="AUTH_ADMIN_GROUPS")
    auth_restricted_roles: str = Field(default="", alias="AUTH_RESTRICTED_ROLES")

    frontend_allowed_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000,http://localhost:8081,http://127.0.0.1:8081",
        alias="FRONTEND_ALLOWED_ORIGINS",
    )
    session_cookie_secure: bool | None = Field(default=None, alias="SESSION_COOKIE_SECURE")
    session_ttl_seconds: int = Field(default=3600, alias="SESSION_TTL_SECONDS")
    auth_state_ttl_seconds: int = Field(default=600, alias="AUTH_STATE_TTL_SECONDS")
    db_pool_min_size: int = Field(default=1, alias="DB_POOL_MIN_SIZE")
    db_pool_max_size: int = Field(default=10, alias="DB_POOL_MAX_SIZE")
    db_pool_timeout_seconds: int = Field(default=10, alias="DB_POOL_TIMEOUT_SECONDS")
    resource_max_cpu_cores: int = Field(default=6, alias="RESOURCE_MAX_CPU_CORES")
    resource_max_ram_gb: int = Field(default=9, alias="RESOURCE_MAX_RAM_GB")
    resource_max_disk_gb: int = Field(default=30, alias="RESOURCE_MAX_DISK_GB")
    vm_min_cpu_cores: int = Field(alias="VM_MIN_CPU_CORES")
    vm_min_ram_gb: int = Field(alias="VM_MIN_RAM_GB")
    vm_min_disk_gb: int = Field(alias="VM_MIN_DISK_GB")
    vm_ipv4_subnet: str | None = Field(default=None, alias="VM_IPV4_SUBNET")
    vm_ipv4_gateway_host: int = Field(default=1, alias="VM_IPV4_GATEWAY_HOST")
    vm_ipv6_subnet: str = Field(default="2001:660:3203:40a::/64", alias="VM_IPV6_SUBNET")
    vm_ipv6_gateway_host: int = Field(default=1, alias="VM_IPV6_GATEWAY_HOST")
    vm_id_min: int = Field(default=2001, alias="VM_ID_MIN")
    proxmox_base_url: str | None = Field(default=None, alias="PROXMOX_BASE_URL")
    proxmox_verify_tls: bool = Field(default=True, alias="PROXMOX_VERIFY_TLS")
    proxmox_timeout_seconds: int = Field(default=10, alias="PROXMOX_TIMEOUT_SECONDS")
    proxmox_task_timeout_seconds: int = Field(default=300, alias="PROXMOX_TASK_TIMEOUT_SECONDS")
    proxmox_executor_max_workers: int = Field(default=16, alias="PROXMOX_EXECUTOR_MAX_WORKERS")
    proxmox_node: str = Field(default="pve", alias="PROXMOX_NODE")
    proxmox_password: str | None = Field(default=None, alias="PROXMOX_PASSWORD")
    proxmox_user: str | None = Field(default=None, alias="PROXMOX_USER")
    proxmox_token_id: str | None = Field(default=None, alias="PROXMOX_TOKEN_ID")
    proxmox_token_secret: str | None = Field(default=None, alias="PROXMOX_TOKEN_SECRET")
    proxmox_service: str = Field(default="PVE", alias="PROXMOX_SERVICE")

    smtp_host: str = Field(default="192.168.102.18", alias="SMTP_HOST")
    smtp_port: int = Field(default=25, alias="SMTP_PORT")
    smtp_from: str = Field(default="hosting@minet.net", alias="SMTP_FROM")

    pdns_api_url: str | None = Field(default=None, alias="PDNS_API_URL")
    pdns_api_key: str | None = Field(default=None, alias="PDNS_API_KEY")
    dns_zone: str = Field(default="h.lan", alias="DNS_ZONE")

    @staticmethod
    def _is_configured(value: str | None) -> bool:
        """Check whether a configuration value is a non-blank string.

        :param value: The configuration value to check.
        :type value: str | None
        :returns: ``True`` if *value* is a non-empty, non-whitespace string.
        :rtype: bool
        """
        return isinstance(value, str) and bool(value.strip())

    @property
    def proxmox_password_configured(self) -> bool:
        """Return ``True`` when Proxmox password auth settings are present.

        :returns: Whether both the base URL and password are configured.
        :rtype: bool
        """
        return self._is_configured(self.proxmox_base_url) and self._is_configured(self.proxmox_password)

    @property
    def proxmox_configured(self) -> bool:
        """Return ``True`` when any Proxmox authentication method is available.

        :returns: Whether Proxmox connectivity is configured.
        :rtype: bool
        """
        return self.proxmox_password_configured

    @property
    def is_production(self) -> bool:
        """Return ``True`` when running in production mode.

        :returns: Whether ``APP_ENV`` is ``"prod"`` or ``"production"``.
        :rtype: bool
        """
        return self.app_env.lower() in {"prod", "production"}

    @property
    def keycloak_issuer(self) -> str:
        """Return the expected issuer URL for access tokens.

        Constructed from the Keycloak server URL and realm name.

        :returns: The Keycloak issuer URL.
        :rtype: str
        """
        return f"{self.keycloak_server_url.rstrip('/')}/realms/{self.keycloak_realm}"

    @property
    def resolved_session_cookie_secure(self) -> bool:
        """Resolve whether the auth session cookie should carry the ``Secure`` flag.

        - If ``SESSION_COOKIE_SECURE`` is explicitly set, that value wins.
        - Otherwise, the ``Secure`` flag is enabled in production only.

        :returns: Whether the session cookie should be marked secure.
        :rtype: bool
        """
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.is_production


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached :class:`Settings` singleton instance.

    The instance is created on first call and reused thereafter.

    :returns: The application settings.
    :rtype: Settings
    """
    return Settings()
