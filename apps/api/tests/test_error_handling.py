"""Tests for application-level error handling and response envelopes."""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from devflow_api.core.errors import AppError, error_payload, register_exception_handlers
from devflow_api.main import create_app


def _make_error_app(exc: Exception) -> FastAPI:
    """Create a minimal FastAPI app that raises the given exception on GET /boom."""
    app = FastAPI()
    register_exception_handlers(app)

    @app.get("/boom")
    async def boom() -> None:
        raise exc

    return app


class TestErrorPayloadHelper:
    def test_returns_error_key(self) -> None:
        payload = error_payload(code="some_error", message="Something went wrong")
        assert "error" in payload

    def test_contains_code_and_message(self) -> None:
        payload = error_payload(code="bad_input", message="Invalid value")
        assert payload["error"]["code"] == "bad_input"  # type: ignore[index]
        assert payload["error"]["message"] == "Invalid value"  # type: ignore[index]

    def test_details_defaults_to_empty_dict(self) -> None:
        payload = error_payload(code="x", message="y")
        assert payload["error"]["details"] == {}  # type: ignore[index]

    def test_details_are_included_when_provided(self) -> None:
        payload = error_payload(code="x", message="y", details={"field": "email"})
        assert payload["error"]["details"] == {"field": "email"}  # type: ignore[index]


class TestAppError:
    def test_default_status_code_is_400(self) -> None:
        err = AppError(code="fail", message="bad")
        assert err.status_code == 400

    def test_custom_status_code(self) -> None:
        err = AppError(code="not_found", message="missing", status_code=404)
        assert err.status_code == 404

    def test_details_defaults_to_empty_dict(self) -> None:
        err = AppError(code="x", message="y")
        assert err.details == {}

    def test_message_is_exception_string(self) -> None:
        err = AppError(code="x", message="something bad")
        assert str(err) == "something bad"


class TestExceptionHandlers:
    def test_app_error_returns_correct_status_code(self) -> None:
        exc = AppError(code="not_found", message="Resource missing", status_code=404)
        with TestClient(_make_error_app(exc)) as client:
            response = client.get("/boom")
        assert response.status_code == 404

    def test_app_error_response_has_error_envelope(self) -> None:
        exc = AppError(code="not_found", message="Resource missing", status_code=404)
        with TestClient(_make_error_app(exc)) as client:
            response = client.get("/boom")
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "not_found"
        assert body["error"]["message"] == "Resource missing"

    def test_http_404_returns_error_envelope(self, client: TestClient) -> None:
        response = client.get("/does-not-exist-at-all")
        assert response.status_code == 404
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "http_error"

    def test_http_error_content_type_is_json(self, client: TestClient) -> None:
        response = client.get("/totally-missing-route")
        assert "application/json" in response.headers["content-type"]

    def test_app_error_content_type_is_json(self) -> None:
        exc = AppError(code="boom", message="error", status_code=500)
        with TestClient(_make_error_app(exc)) as client:
            response = client.get("/boom")
        assert "application/json" in response.headers["content-type"]


class TestCreateApp:
    def test_app_title_is_set(self) -> None:
        app = create_app()
        assert app.title == "DevFlow Insight API"

    def test_app_has_exception_handlers_registered(self) -> None:
        """The app should handle AppError gracefully (not return 500)."""
        app = create_app()

        @app.get("/test-error")
        async def raise_app_error() -> None:
            raise AppError(code="test", message="test error", status_code=400)

        with TestClient(app) as client:
            response = client.get("/test-error")
        assert response.status_code == 400
        assert response.json()["error"]["code"] == "test"
