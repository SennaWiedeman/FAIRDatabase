import pytest
from app import get_db


@pytest.fixture(scope="module")
def pbpk_client(app):
    """Test client with session seeded as a logged-in user for stress tests."""
    from config import supabase_extension

    TEST_EMAIL = "pbpk_stress@test.com"
    TEST_PASSWORD = "aBJ3%!fj0_f42h2pvw3"

    client = app.test_client()
    client.post(
        "/auth/register",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        follow_redirects=True,
    )
    client.post(
        "/auth/login",
        data={"email": TEST_EMAIL, "password": TEST_PASSWORD},
        follow_redirects=True,
    )

    with app.app_context():
        users = supabase_extension.client.auth.admin.list_users()
        user = next((u for u in users if u.email == TEST_EMAIL), None)

    yield client, TEST_EMAIL

    with app.app_context():
        if user:
            supabase_extension.client.auth.admin.delete_user(user.id)


@pytest.fixture(scope="module")
def pbpk_cleanup(app):
    """Collects IDs created during stress tests and deletes them on teardown."""
    ps_ids: list[int] = []
    run_ids: list[int] = []

    yield ps_ids, run_ids

    with app.app_context():
        db = get_db()
        cur = db.cursor()
        if run_ids:
            cur.execute(
                "DELETE FROM _fd.pbpk_simulation_runs WHERE id = ANY(%s)", (run_ids,)
            )
        if ps_ids:
            cur.execute(
                "DELETE FROM _fd.pbpk_parameter_sets WHERE id = ANY(%s)", (ps_ids,)
            )
        db.commit()
        cur.close()
