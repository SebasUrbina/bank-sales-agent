from bank_sales_agent.infrastructure.api.app import create_app
from bank_sales_agent.infrastructure.config.settings import Settings


def test_api_settings_configure_fastapi() -> None:
    app = create_app(
        Settings(
            api={
                "title": "Sales Agent QA",
                "version": "2.0.0",
                "docs_enabled": False,
            }
        )
    )

    assert app.title == "Sales Agent QA"
    assert app.version == "2.0.0"
    assert app.docs_url is None
    assert app.openapi_url is None
