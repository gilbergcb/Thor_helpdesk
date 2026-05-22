import httpx
from pydantic import AnyHttpUrl

from app.core.config import get_settings


class ZApiClient:
    def __init__(self) -> None:
        self.settings = get_settings()
        self._path_instance_id, self._path_token = self._credentials_from_url(
            self.settings.zapi_base_url
        )

    @staticmethod
    def _credentials_from_url(url: AnyHttpUrl | None) -> tuple[str | None, str | None]:
        if not url:
            return None, None
        parts = str(url).rstrip("/").split("/")
        try:
            instance_index = parts.index("instances")
            token_index = parts.index("token")
        except ValueError:
            return None, None
        instance_id = parts[instance_index + 1] if len(parts) > instance_index + 1 else None
        token = parts[token_index + 1] if len(parts) > token_index + 1 else None
        return instance_id, token

    def _api_root(self) -> str:
        if not self.settings.zapi_base_url:
            raise RuntimeError("Z-API base URL is not configured")
        root = str(self.settings.zapi_base_url).rstrip("/")
        marker = "/instances/"
        if marker in root:
            root = root.split(marker, 1)[0]
        return root

    def _url(self, endpoint: str) -> str:
        instance_id = self.settings.zapi_instance_id or self._path_instance_id
        token = self.settings.zapi_token or self._path_token
        if self._path_token and token == instance_id:
            token = self._path_token
        if not (instance_id and token):
            raise RuntimeError("Z-API instance ID or token is not configured")
        return (
            f"{self._api_root()}/instances/"
            f"{instance_id}/token/{token}/{endpoint}"
        )

    def _headers(self) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.settings.zapi_client_token:
            headers["Client-Token"] = self.settings.zapi_client_token
        return headers

    async def send_group_message(
        self,
        group_id: str,
        message: str,
        mentioned: list[str] | None = None,
    ) -> dict:
        payload = {"phone": group_id, "message": message}
        if mentioned:
            payload["mentioned"] = mentioned
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.post(
                self._url("send-text"),
                json=payload,
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()

    async def list_groups(self, page: int = 1, page_size: int = 20) -> list[dict]:
        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                self._url("groups"),
                params={"page": page, "pageSize": page_size},
                headers=self._headers(),
            )
            response.raise_for_status()
            return response.json()
