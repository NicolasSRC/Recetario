from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, database_url="sqlite://")  # type: ignore[call-arg]
    app = create_app(settings)
    with TestClient(app) as test_client:
        yield test_client


def _payload(**overrides: Any) -> dict[str, Any]:
    data: dict[str, Any] = {
        "title": "Tortilla de patatas",
        "description": "La clásica tortilla española.",
        "language": "es",
        "servings": 4,
        "prep_time_min": 10,
        "cook_time_min": 30,
        "difficulty": "facil",
        "ingredients": [
            {"name": "patata", "quantity": 4, "unit": "unidad", "raw_text": "4 patatas"},
            {"name": "huevo", "quantity": 5, "unit": "unidad", "raw_text": "5 huevos"},
        ],
        "steps": [
            {"order": 1, "text": "Pelar y cortar las patatas."},
            {"order": 2, "text": "Freír y mezclar con el huevo batido."},
        ],
        "tags": ["huevo", "española"],
    }
    data.update(overrides)
    return data


def test_crear_receta_manual(client: TestClient) -> None:
    response = client.post("/api/v1/recipes", json=_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["title"] == "Tortilla de patatas"
    assert body["status"] == "aprobada"
    assert body["id"]


def test_listar_recetas(client: TestClient) -> None:
    client.post("/api/v1/recipes", json=_payload())

    response = client.get("/api/v1/recipes")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


def test_detalle_de_receta(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.get(f"/api/v1/recipes/{recipe_id}")

    assert response.status_code == 200
    assert response.json()["title"] == "Tortilla de patatas"


def test_detalle_inexistente(client: TestClient) -> None:
    assert client.get("/api/v1/recipes/no-existe").status_code == 404


def test_editar_titulo(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.patch(
        f"/api/v1/recipes/{recipe_id}", json={"title": "Tortilla de patata y cebolla"}
    )

    assert response.status_code == 200
    assert response.json()["title"] == "Tortilla de patata y cebolla"


def test_editar_ingredientes(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={
            "ingredients": [
                {"name": "cebolla", "quantity": 1, "unit": "unidad", "raw_text": "1 cebolla"}
            ]
        },
    )

    assert response.status_code == 200
    ingredients = response.json()["ingredients"]
    assert len(ingredients) == 1
    assert ingredients[0]["name"] == "cebolla"


def test_editar_pasos(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.patch(
        f"/api/v1/recipes/{recipe_id}",
        json={"steps": [{"order": 1, "text": "Mezclar todo y cuajar."}]},
    )

    assert response.status_code == 200
    assert len(response.json()["steps"]) == 1


def test_cambiar_estado_a_aprobada(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.patch(f"/api/v1/recipes/{recipe_id}", json={"status": "por_revisar"})

    assert response.status_code == 200
    assert response.json()["status"] == "por_revisar"


def test_borrar_receta(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    assert client.delete(f"/api/v1/recipes/{recipe_id}").status_code == 204
    assert client.get(f"/api/v1/recipes/{recipe_id}").status_code == 404


def test_exportar_jsonld(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.get(f"/api/v1/recipes/{recipe_id}/export?format=jsonld")

    assert response.status_code == 200
    body = response.json()
    assert body["@type"] == "Recipe"
    assert body["name"] == "Tortilla de patatas"
    assert body["recipeIngredient"] == ["4 patatas", "5 huevos"]
    assert body["recipeInstructions"][0]["position"] == 1


def test_exportar_markdown(client: TestClient) -> None:
    recipe_id = client.post("/api/v1/recipes", json=_payload()).json()["id"]

    response = client.get(f"/api/v1/recipes/{recipe_id}/export?format=md")

    assert response.status_code == 200
    assert "# Tortilla de patatas" in response.text
    assert "## Ingredientes" in response.text


def test_buscar_por_ingrediente(client: TestClient) -> None:
    client.post("/api/v1/recipes", json=_payload())

    response = client.get("/api/v1/recipes", params={"q": "patata"})

    assert response.status_code == 200
    assert response.json()["total"] == 1


def test_duplicado_por_url(client: TestClient) -> None:
    payload = _payload(source_url="https://www.tiktok.com/@chef/video/1")

    assert client.post("/api/v1/recipes", json=payload).status_code == 201
    assert client.post("/api/v1/recipes", json=payload).status_code == 409


def test_receta_invalida(client: TestClient) -> None:
    response = client.post("/api/v1/recipes", json=_payload(ingredients=[]))
    assert response.status_code == 422


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}
