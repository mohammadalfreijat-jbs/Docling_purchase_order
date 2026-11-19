"""Thin wrapper around DoclingServiceClient for PDF-to-markdown conversion."""

from pathlib import Path

from docling.service_client import DoclingServiceClient

from app.config import config


class DoclingClient:
    """Convert a PDF file to markdown using the Docling watsonx SaaS API."""

    def convert(self, pdf_path: Path) -> str:
        """Return the markdown representation of *pdf_path*.

        Raises:
            RuntimeError: if the Docling API call fails.
        """
        try:
            with DoclingServiceClient(
                url=config.SERVICE_URL,
                api_key=config.API_KEY,
            ) as client:
                result = client.convert(source=pdf_path)
            return result.document.export_to_markdown()
        except Exception as exc:
            raise RuntimeError(f"Docling conversion failed: {exc}") from exc
