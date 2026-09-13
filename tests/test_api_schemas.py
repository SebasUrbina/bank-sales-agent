from bank_sales_agent.infrastructure.api.schemas import AgentRequest


def test_agent_request_accepts_normalized_apps_script_payload() -> None:
    request = AgentRequest.model_validate(
        {
            "message": "Resume este archivo",
            "space_name": "spaces/AAAA",
            "thread_name": "spaces/AAAA/threads/BBBB",
            "user_email": "ejecutivo@bank.test",
            "user_oauth_token": "secret-token",
            "attachments": [
                {
                    "resource_name": "spaces/AAAA/attachments/CCCC",
                    "file_name": "movimientos.pdf",
                    "mime_type": "application/pdf",
                }
            ],
        }
    )

    assert request.attachments[0].file_name == "movimientos.pdf"
    assert "secret-token" not in repr(request)
    assert request.user_oauth_token.get_secret_value() == "secret-token"
