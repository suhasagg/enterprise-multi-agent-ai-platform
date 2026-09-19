from fastapi.testclient import TestClient
# Integration test skeleton: requires DB/config before importing app in CI.
def test_contract_shape():
    payload = {"message": "hello", "session_id": "s1"}
    assert payload["session_id"] == "s1"
