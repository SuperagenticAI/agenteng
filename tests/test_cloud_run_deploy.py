"""Exercise deployment orchestration with a fake gcloud; never contact Google."""

import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "deploy/deploy-cloud-run.sh"
GENERATED_URL = "https://agenteng-example-ew.a.run.app"


@pytest.fixture
def deployment(tmp_path):
    binary = tmp_path / "bin"
    binary.mkdir()
    fake = binary / "gcloud"
    fake.write_text(
        f"#!{sys.executable}\n"
        + textwrap.dedent(
            """
            import json, os, sys
            from pathlib import Path
            root = Path(os.environ['FAKE_ROOT'])
            args = sys.argv[1:]
            with (root / 'calls.jsonl').open('a') as output:
                output.write(json.dumps(args) + '\\n')
            if args[:3] == ['run', 'services', 'describe']:
                if os.environ.get('FAKE_EXISTS') != '1' and not (root / 'created').exists():
                    sys.exit(1)
                print(os.environ['FAKE_URL'])
            elif args[:2] == ['run', 'deploy']:
                if os.environ.get('FAKE_DEPLOY_FAIL') == '1':
                    sys.exit(1)
                (root / 'created').touch()
            elif args[:3] == ['run', 'services', 'update-traffic']:
                if os.environ.get('FAKE_TRAFFIC_FAIL') == '1':
                    sys.exit(1)
            elif args[:3] != ['run', 'services', 'update']:
                sys.exit('Unexpected command')
            """
        )
    )
    fake.chmod(0o755)
    env = {
        **os.environ,
        "PATH": str(binary) + os.pathsep + os.environ["PATH"],
        "FAKE_ROOT": str(tmp_path),
        "FAKE_URL": GENERATED_URL,
        "DEPLOY_PROJECT": "example-project",
        "DEPLOY_REGION": "europe-west1",
        "DEPLOY_SERVICE": "agenteng",
        "DEPLOY_IMAGE": "europe-west1-docker.pkg.dev/example-project/cloud-run-source-deploy/agenteng:v0.0.1",
        "DEPLOY_RUNTIME_ACCOUNT": "agenteng-runtime@example-project.iam.gserviceaccount.com",
        "DEPLOY_PUBLIC_URL": "",
        "DEPLOY_URL_FILE": str(tmp_path / "deployed-url"),
    }

    def run(**overrides):
        result = subprocess.run(
            ["bash", str(SCRIPT)],
            cwd=tmp_path,
            env={**env, **overrides},
            text=True,
            capture_output=True,
        )
        log = tmp_path / "calls.jsonl"
        calls = [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []
        return result, calls, tmp_path / "deployed-url"

    return run


def test_first_deployment_bootstraps_generated_origin(deployment):
    result, calls, url = deployment()
    assert result.returncode == 0, result.stderr
    deploy = next(c for c in calls if c[:2] == ["run", "deploy"])
    assert "--service-account=agenteng-runtime@example-project.iam.gserviceaccount.com" in deploy
    assert "--no-invoker-iam-check" in deploy
    assert "--min-instances=0" in deploy and "--max-instances=2" in deploy
    env = next(c for c in deploy if c.startswith("--update-env-vars="))
    assert not any(c.startswith("--set-env-vars=") for c in deploy)
    assert "AGENTENG_ENABLE_" not in env
    assert "AGENTENG_MODEL" not in env
    assert not any(c.startswith(("--set-secrets=", "--clear-secrets")) for c in deploy)
    dockerfile = (SCRIPT.parents[1] / "Dockerfile").read_text()
    for flag in ["CHAT", "STANDARD", "RLM"]:
        assert f"AGENTENG_ENABLE_{flag}=0" in dockerfile
    updates = [c for c in calls if c[:3] == ["run", "services", "update"]]
    assert len(updates) == 1
    assert "--update-env-vars=AGENTENG_PUBLIC_URL=" + GENERATED_URL in updates[0]
    assert url.read_text().strip() == GENERATED_URL
    assert calls[-1][:3] == ["run", "services", "update-traffic"]
    assert "--to-latest" in calls[-1]


def test_existing_service_reuses_generated_origin_without_extra_revision(deployment):
    result, calls, url = deployment(FAKE_EXISTS="1")
    assert result.returncode == 0, result.stderr
    assert not any(c[:3] == ["run", "services", "update"] for c in calls)
    deploy = next(c for c in calls if c[:2] == ["run", "deploy"])
    assert any("AGENTENG_PUBLIC_URL=" + GENERATED_URL in c for c in deploy)
    assert url.read_text().strip() == GENERATED_URL


def test_configured_domain_is_preserved_and_normalized(deployment):
    result, calls, url = deployment(DEPLOY_PUBLIC_URL="https://a2a.agentengineering.world/")
    assert result.returncode == 0, result.stderr
    assert len(calls) == 2 and calls[0][:2] == ["run", "deploy"]
    assert url.read_text() == "https://a2a.agentengineering.world\n"
    assert any("AGENTENG_PUBLIC_URL=https://a2a.agentengineering.world," in c for c in calls[0])


@pytest.mark.parametrize(
    "origin",
    [
        "http://example.com",
        "https://example.com/path",
        "https://user@example.com",
        "https://example.com,AGENTENG_ENABLE_INTAKE=1",
    ],
)
def test_invalid_origin_fails_before_any_cloud_operation(deployment, origin):
    result, calls, url = deployment(DEPLOY_PUBLIC_URL=origin)
    assert result.returncode != 0
    assert calls == [] and not url.exists()


def test_failed_deployment_does_not_record_a_successful_url(deployment):
    result, calls, url = deployment(FAKE_DEPLOY_FAIL="1")
    assert result.returncode != 0
    assert not any(c[:3] == ["run", "services", "update"] for c in calls)
    assert not url.exists()


def test_missing_generated_url_fails_without_routing_or_success_record(deployment):
    result, calls, url = deployment(FAKE_URL="")
    assert result.returncode != 0
    assert "did not return a service URL" in result.stderr
    assert not any(c[:3] == ["run", "services", "update-traffic"] for c in calls)
    assert not url.exists()


def test_failed_traffic_update_does_not_record_a_successful_url(deployment):
    result, calls, url = deployment(FAKE_TRAFFIC_FAIL="1")
    assert result.returncode != 0
    assert calls[-1][:3] == ["run", "services", "update-traffic"]
    assert not url.exists()


def test_cloudbuild_defaults_public_url_to_custom_domain():
    """Tag deploys must keep the production origin unless a trigger overrides it."""
    config = (SCRIPT.parents[1] / "cloudbuild.yaml").read_text()
    assert "  _PUBLIC_URL: 'https://a2a.agentengineering.world'\n" in config
    assert "DEPLOY_PUBLIC_URL=${_PUBLIC_URL}" in config
