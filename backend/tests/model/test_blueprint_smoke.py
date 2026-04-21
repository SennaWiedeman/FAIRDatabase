class TestModelBlueprintRegistered:
    def test_scenarios_unauthenticated_redirects(self, client):
        """Verifies model_routes blueprint is registered and auth guard works."""
        resp = client.get("/model/scenarios")
        assert resp.status_code == 302

    def test_parameter_sets_unauthenticated_redirects(self, client):
        resp = client.get("/model/parameter-sets")
        assert resp.status_code == 302

    def test_runs_unauthenticated_redirects(self, client):
        resp = client.get("/model/runs/1")
        assert resp.status_code == 302
