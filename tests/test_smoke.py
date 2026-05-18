from __future__ import annotations

from main import app


async def test_pages_render():
    """Les pages publiques se rendent sans erreur de template."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        for path in ("/", "/about", "/stats"):
            resp = await client.get(path)
            assert resp.status_code == 200, f"{path} -> {resp.status_code}"


async def test_health_endpoint():
    """La sonde de santé répond et renvoie ses checks."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/api/v1/health")
        assert resp.status_code in (200, 503)
        data = await resp.get_json()
        assert "checks" in data["data"]


async def test_unknown_page_404():
    """Une page inconnue renvoie la page d'erreur 404."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/page-qui-nexiste-pas")
        assert resp.status_code == 404


async def test_nodes_endpoint():
    """L'API liste au moins un nœud."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/api/v1/nodes")
        assert resp.status_code == 200
        data = await resp.get_json()
        assert len(data["data"]["nodes"]) >= 1


async def test_run_rejects_malformed_request():
    """Une requête mal formée est rejetée en 400."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.post("/api/v1/run", json={"tool": "ping"})
        assert resp.status_code == 400


async def test_run_rejects_private_target():
    """Une cible privée est rejetée en 422 avant toute exécution."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.post("/api/v1/run", json={
            "node_id": "local", "tool": "ping", "target": "192.168.1.1", "family": "auto",
        })
        assert resp.status_code == 422


async def test_run_rejects_injection_target():
    """Une cible avec métacaractères shell est rejetée."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.post("/api/v1/run", json={
            "node_id": "local", "tool": "ping", "target": "8.8.8.8; id", "family": "auto",
        })
        assert resp.status_code == 422


async def test_stats_endpoint():
    """L'API de statistiques renvoie les agrégats."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = await resp.get_json()
        assert "total" in data["data"]
        assert "by_tool" in data["data"]
        assert "recent" in data["data"]


async def test_speedtest_disabled_by_default():
    """Le speedtest est désactivé par défaut et renvoie 404."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/api/v1/speedtest/10mb")
        assert resp.status_code == 404


async def test_speedtest_cli_token_disabled_by_default():
    """La génération de token CLI est refusée tant que le speedtest est désactivé."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.post("/api/v1/speedtest/cli-token", json={"file_id": "10mb"})
        assert resp.status_code == 404


async def test_speedtest_cli_download_rejects_invalid_token():
    """Le téléchargement CLI refuse un token absent ou invalide."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/api/v1/speedtest/cli/10mb?token=inexistant")
        assert resp.status_code in (403, 404)


async def test_speedtest_cli_script_rejects_invalid_os():
    """Le script CLI refuse un système d'exploitation inconnu."""
    async with app.test_app() as test_app:
        client = test_app.test_client()
        resp = await client.get("/api/v1/speedtest/cli/script/10mb?token=x&os=plan9")
        assert resp.status_code == 404
