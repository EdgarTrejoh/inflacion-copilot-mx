import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_api_dockerfile_is_isolated_and_uses_cloud_run_port():
    dockerfile = read("Dockerfile.api")

    assert "FROM python:3.12-slim" in dockerfile
    assert "requirements.api.txt" in dockerfile
    assert "api.main:app" in dockerfile
    assert "${PORT:-8080}" in dockerfile
    assert "USER app" in dockerfile
    assert "COPY . ." not in dockerfile
    assert "streamlit run" not in dockerfile
    assert "frontend" not in dockerfile


def test_api_requirements_exclude_development_and_ui_only_packages():
    requirements = read("requirements.api.txt").lower()

    assert "fastapi==" in requirements
    assert "uvicorn==" in requirements
    assert "google-cloud-bigquery==" in requirements
    assert "google-cloud-aiplatform==" in requirements
    assert "plotly" not in requirements
    assert "pytest" not in requirements
    assert "httpx2" not in requirements


def test_docker_context_excludes_frontend_tests_and_local_secrets():
    dockerignore = read(".dockerignore").splitlines()

    assert ".env" in dockerignore
    assert ".env.*" in dockerignore
    assert "frontend/" in dockerignore
    assert "tests/" in dockerignore
    assert ".git/" in dockerignore


def test_firebase_serves_vite_dist_and_orders_api_before_spa_fallback():
    config = json.loads(read("firebase.json"))
    hosting = config["hosting"]

    assert hosting["public"] == "frontend/dist"
    assert "**/node_modules/**" in hosting["ignore"]
    assert hosting["rewrites"][0] == {
        "source": "/api/**",
        "run": {
            "serviceId": "inflacion-copilot-api-beta",
            "region": "us-central1",
        },
    }
    assert hosting["rewrites"][1] == {
        "source": "**",
        "destination": "/index.html",
    }


def test_frontend_defaults_to_relative_api_and_production_example_matches():
    client = read("frontend/src/services/api.ts")
    production_env = read("frontend/.env.production.example")

    assert '|| "/api"' in client
    assert production_env.strip() == "VITE_API_BASE_URL=/api"
    assert "http://" not in production_env
    assert "https://" not in production_env


def test_cloud_run_reference_enforces_request_billing_and_scale_to_zero():
    guide = read("deployment/PARALLEL_DEPLOYMENT.md")

    assert "--cpu-throttling" in guide
    assert re.search(r"--min\s+0", guide)
    assert "--max $MaxInstances" in guide
    assert "--service-account $RuntimeServiceAccount" in guide
    assert "--no-allow-unauthenticated" in guide
    assert "firebase deploy --only hosting" in guide


def test_deployment_templates_do_not_contain_common_secret_formats():
    artifact_paths = [
        "Dockerfile.api",
        "requirements.api.txt",
        "firebase.json",
        "frontend/.env.production.example",
        "deployment/cloud-run.env.example.yaml",
        "deployment/PARALLEL_DEPLOYMENT.md",
    ]
    combined = "\n".join(read(path) for path in artifact_paths)

    forbidden_patterns = [
        r"-----BEGIN (?:RSA |EC )?PRIVATE KEY-----",
        r"AIza[0-9A-Za-z_-]{30,}",
        r"sk-(?:proj-)?[0-9A-Za-z_-]{20,}",
        r'"private_key"\s*:',
    ]
    for pattern in forbidden_patterns:
        assert re.search(pattern, combined) is None
