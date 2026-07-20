from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Azure OpenAI
    azure_openai_endpoint:   Optional[str] = None
    azure_openai_key:        Optional[str] = None
    azure_openai_deployment: str = "banking-doc-extractor"

    # Fallback: plain OpenAI or Groq
    openai_api_key:  Optional[str] = None
    openai_base_url: str = "[api.openai.com](https://api.openai.com/v1)"
    openai_model:    str = "gpt-4.1-mini"

    # Azure Document Intelligence
    azure_doc_intel_endpoint: Optional[str] = None
    azure_doc_intel_key:      Optional[str] = None

    # Azure Blob Storage
    azure_storage_connection_string: Optional[str] = None
    azure_storage_container: str = "documents"

    # Azure Cosmos DB
    cosmos_endpoint:  Optional[str] = None
    cosmos_key:       Optional[str] = None
    cosmos_database:  str = "idp-db"
    cosmos_container: str = "documents"

    @property
    def use_azure_openai(self) -> bool:
        return bool(self.azure_openai_endpoint and self.azure_openai_key)

    @property
    def use_doc_intel(self) -> bool:
        return bool(self.azure_doc_intel_endpoint and self.azure_doc_intel_key)

    @property
    def use_cosmos(self) -> bool:
        return bool(self.cosmos_endpoint and self.cosmos_key)

    @property
    def use_blob(self) -> bool:
        return bool(self.azure_storage_connection_string)

    @property
    def llm_label(self) -> str:
        if self.use_azure_openai:
            return f"Azure OpenAI / {self.azure_openai_deployment}"
        if "groq" in (self.openai_base_url or ""):
            return f"Groq / {self.openai_model}"
        return f"OpenAI / {self.openai_model}"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
