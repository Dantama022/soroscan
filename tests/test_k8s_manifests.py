"""Test suite enforcing Kubernetes manifest invariants for SoroScan.

Enforces:
- Health probes: serving workloads must define readinessProbe (/ready/) and
  livenessProbe (/health/).
- Resources: every container and initContainer must declare cpu and memory
  requests and limits, with requests <= limits.
- Security Context: every pod and container must enforce non-root execution,
  privilege escalation disabled, dropped capabilities, and valid
  fsGroup/runAsUser.
- Image pull policy: every container and initContainer must explicitly declare
  imagePullPolicy.
- Regression tests: explicitly asserts that regressions like #1632 (wrong probe
  path) and #1633 (missing security context) fail the invariant checks.
"""

import copy
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
K8S_DIR = REPO_ROOT / "k8s"

WORKLOAD_KINDS = {"Deployment", "CronJob", "StatefulSet", "DaemonSet", "Job"}


def load_all_k8s_manifests(directory: Path = K8S_DIR):
    """Load and parse all YAML files in the given directory."""
    manifests = []
    yaml_files = sorted(
        list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))
    )
    for file_path in yaml_files:
        with open(file_path, "r", encoding="utf-8") as f:
            for doc in yaml.safe_load_all(f):
                if doc and isinstance(doc, dict):
                    manifests.append((file_path.name, doc))
    return manifests


def extract_workload_specs(manifests):
    """Extract workload information including pod spec and containers."""
    workloads = []
    for filename, doc in manifests:
        kind = doc.get("kind")
        if kind not in WORKLOAD_KINDS:
            continue

        metadata = doc.get("metadata", {})
        name = metadata.get("name", "unnamed")
        namespace = metadata.get("namespace", "default")

        # Extract pod spec based on workload kind
        if kind == "CronJob":
            pod_spec = (
                doc.get("spec", {})
                .get("jobTemplate", {})
                .get("spec", {})
                .get("template", {})
                .get("spec", {})
            )
        else:
            pod_spec = doc.get("spec", {}).get("template", {}).get("spec", {})

        workloads.append(
            {
                "filename": filename,
                "kind": kind,
                "name": name,
                "namespace": namespace,
                "pod_spec": pod_spec,
                "raw_doc": doc,
            }
        )
    return workloads


def get_all_containers(pod_spec):
    """Return list of (container_type, container_dict)."""
    containers = []
    for c in pod_spec.get("initContainers", []):
        containers.append(("initContainer", c))
    for c in pod_spec.get("containers", []):
        containers.append(("container", c))
    return containers


def parse_cpu(val):
    """Parse CPU string (e.g. '100m', '1', '0.5') to float millicores."""
    if isinstance(val, (int, float)):
        return float(val) * 1000.0
    val_str = str(val).strip()
    if val_str.endswith("m"):
        return float(val_str[:-1])
    return float(val_str) * 1000.0


def parse_memory(val):
    """Parse memory string (e.g. '256Mi', '1Gi', '512M') to float bytes."""
    if isinstance(val, (int, float)):
        return float(val)
    val_str = str(val).strip()
    units = {
        "Ki": 1024,
        "Mi": 1024**2,
        "Gi": 1024**3,
        "Ti": 1024**4,
        "k": 1000,
        "M": 1000**2,
        "G": 1000**3,
        "T": 1000**4,
    }
    for unit, factor in units.items():
        if val_str.endswith(unit):
            number_part = float(val_str[: -len(unit)])
            return number_part * factor
    return float(val_str)


# ============================================================================
# Invariant Assertions
# ============================================================================


def assert_probes_invariant(workload):
    """Assert health probes invariant on serving workloads."""
    name = workload["name"]
    pod_spec = workload["pod_spec"]

    # Only the API backend deployment serves live HTTP traffic with ingress probes
    if "backend" in name:
        containers = [
            c
            for _, c in get_all_containers(pod_spec)
            if c.get("name") == "backend"
        ]
        assert len(containers) == 1, f"Expected 1 'backend' container in {name}"
        backend_container = containers[0]

        # Readiness probe check
        assert "readinessProbe" in backend_container, (
            f"Workload {name} missing readinessProbe"
        )
        readiness = backend_container["readinessProbe"]
        assert "httpGet" in readiness, (
            f"Workload {name} readinessProbe must use httpGet"
        )
        ready_path = readiness["httpGet"].get("path")
        assert ready_path == "/ready/", (
            f"Workload {name} readinessProbe path must be '/ready/', "
            f"got '{ready_path}' (Regression #1632)"
        )
        assert readiness.get("initialDelaySeconds", 0) > 0
        assert readiness.get("periodSeconds", 0) > 0
        assert readiness.get("timeoutSeconds", 0) > 0

        # Liveness probe check
        assert "livenessProbe" in backend_container, (
            f"Workload {name} missing livenessProbe"
        )
        liveness = backend_container["livenessProbe"]
        assert "httpGet" in liveness, (
            f"Workload {name} livenessProbe must use httpGet"
        )
        live_path = liveness["httpGet"].get("path")
        assert live_path == "/health/", (
            f"Workload {name} livenessProbe path must be '/health/', "
            f"got '{live_path}' (Regression #1632)"
        )
        assert liveness.get("initialDelaySeconds", 0) > 0
        assert liveness.get("periodSeconds", 0) > 0
        assert liveness.get("timeoutSeconds", 0) > 0


def assert_resources_invariant(container, context_name):
    """Assert resource requests and limits invariant for a container."""
    c_name = container.get("name", "unnamed")
    assert "resources" in container, (
        f"Container '{c_name}' in '{context_name}' missing 'resources'"
    )
    resources = container["resources"]
    assert isinstance(resources, dict), (
        f"'resources' in '{c_name}' must be a dict"
    )

    # Check requests
    assert "requests" in resources, (
        f"Container '{c_name}' in '{context_name}' missing 'resources.requests'"
    )
    requests = resources["requests"]
    assert "cpu" in requests, f"Container '{c_name}' missing requests.cpu"
    assert "memory" in requests, f"Container '{c_name}' missing requests.memory"

    # Check limits
    assert "limits" in resources, (
        f"Container '{c_name}' in '{context_name}' missing 'resources.limits'"
    )
    limits = resources["limits"]
    assert "cpu" in limits, f"Container '{c_name}' missing limits.cpu"
    assert "memory" in limits, f"Container '{c_name}' missing limits.memory"

    req_cpu = parse_cpu(requests["cpu"])
    lim_cpu = parse_cpu(limits["cpu"])
    assert req_cpu <= lim_cpu, (
        f"Container '{c_name}' cpu request ({requests['cpu']}) "
        f"exceeds limit ({limits['cpu']})"
    )

    req_mem = parse_memory(requests["memory"])
    lim_mem = parse_memory(limits["memory"])
    assert req_mem <= lim_mem, (
        f"Container '{c_name}' memory request ({requests['memory']}) "
        f"exceeds limit ({limits['memory']})"
    )


def assert_security_context_invariant(pod_spec, container, context_name):
    """Assert security context invariant for pod and container."""
    # Pod securityContext
    pod_sc = pod_spec.get("securityContext")
    assert pod_sc is not None, (
        f"Workload '{context_name}' missing pod-level securityContext "
        f"(Regression #1633)"
    )
    assert isinstance(pod_sc, dict), (
        f"Pod securityContext in '{context_name}' must be a dict"
    )
    assert "fsGroup" in pod_sc, (
        f"Pod securityContext in '{context_name}' must specify fsGroup"
    )
    assert isinstance(pod_sc["fsGroup"], int) and pod_sc["fsGroup"] > 0

    # Container securityContext
    c_name = container.get("name", "unnamed")
    c_sc = container.get("securityContext")
    assert c_sc is not None, (
        f"Container '{c_name}' in '{context_name}' missing container-level "
        f"securityContext (Regression #1633)"
    )
    assert isinstance(c_sc, dict), (
        f"Container securityContext in '{c_name}' must be a dict"
    )

    assert c_sc.get("allowPrivilegeEscalation") is False, (
        f"Container '{c_name}' in '{context_name}' must have "
        f"allowPrivilegeEscalation=false"
    )
    assert c_sc.get("runAsNonRoot") is True, (
        f"Container '{c_name}' in '{context_name}' must have runAsNonRoot=true"
    )
    valid_user = (
        "runAsUser" in c_sc
        and isinstance(c_sc["runAsUser"], int)
        and c_sc["runAsUser"] > 0
    )
    assert valid_user, (
        f"Container '{c_name}' in '{context_name}' must have valid runAsUser"
    )

    capabilities = c_sc.get("capabilities", {})
    drop = capabilities.get("drop", [])
    assert "ALL" in drop, (
        f"Container '{c_name}' in '{context_name}' capabilities.drop must "
        f"include 'ALL'"
    )


def assert_image_pull_policy_invariant(container, context_name):
    """Assert image pull policy invariant for a container."""
    c_name = container.get("name", "unnamed")
    assert "imagePullPolicy" in container, (
        f"Container '{c_name}' in '{context_name}' missing imagePullPolicy"
    )
    policy = container["imagePullPolicy"]
    assert policy in {"IfNotPresent", "Always", "Never"}, (
        f"Container '{c_name}' in '{context_name}' invalid imagePullPolicy "
        f"'{policy}'"
    )


# ============================================================================
# Test Cases on Actual Manifests
# ============================================================================


class TestKubernetesManifestInvariants:
    """Verifies that all actual manifests in k8s/ conform to invariants."""

    @pytest.fixture(scope="class")
    def workloads(self):
        manifests = load_all_k8s_manifests()
        assert len(manifests) > 0, "No Kubernetes manifests found in k8s/"
        workloads = extract_workload_specs(manifests)
        assert len(workloads) > 0, "No workload resources found in k8s/"
        return workloads

    def test_all_manifest_files_exist_and_load(self):
        manifests = load_all_k8s_manifests()
        filenames = {fn for fn, _ in manifests}
        expected_workload_files = {
            "backend-deployment.yaml",
            "worker-deployment.yaml",
            "beat-cronjob.yaml",
            "backup-cronjob.yaml",
        }
        assert expected_workload_files.issubset(filenames)

    def test_health_probes_on_serving_workloads(self, workloads):
        for w in workloads:
            assert_probes_invariant(w)

    def test_resource_requests_and_limits_on_all_containers(self, workloads):
        for w in workloads:
            context = f"{w['filename']}:{w['kind']}/{w['name']}"
            for c_type, container in get_all_containers(w["pod_spec"]):
                assert_resources_invariant(container, f"{context}:{c_type}")

    def test_security_context_on_all_workloads_and_containers(self, workloads):
        for w in workloads:
            context = f"{w['filename']}:{w['kind']}/{w['name']}"
            for c_type, container in get_all_containers(w["pod_spec"]):
                assert_security_context_invariant(
                    w["pod_spec"], container, f"{context}:{c_type}"
                )

    def test_image_pull_policy_on_all_containers(self, workloads):
        for w in workloads:
            context = f"{w['filename']}:{w['kind']}/{w['name']}"
            for c_type, container in get_all_containers(w["pod_spec"]):
                assert_image_pull_policy_invariant(
                    container, f"{context}:{c_type}"
                )


# ============================================================================
# Regression and Negative Tests
# ============================================================================


class TestRegressionFailures:
    """Explicitly verify that invariant tests fail on known regressions."""

    @pytest.fixture
    def valid_backend_workload(self):
        manifests = load_all_k8s_manifests()
        workloads = extract_workload_specs(manifests)
        backend = next(w for w in workloads if w["name"] == "soroscan-backend")
        return copy.deepcopy(backend)

    def test_regression_1632_wrong_readiness_probe_path_fails(
        self, valid_backend_workload
    ):
        """Regression #1632: readiness probe pointing to /api/events/."""
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        backend_container["readinessProbe"]["httpGet"]["path"] = "/api/events/"

        with pytest.raises(AssertionError, match="Regression #1632"):
            assert_probes_invariant(valid_backend_workload)

    def test_regression_1632_wrong_liveness_probe_path_fails(
        self, valid_backend_workload
    ):
        """Regression #1632: liveness probe pointing to /api/events/."""
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        backend_container["livenessProbe"]["httpGet"]["path"] = "/api/events/"

        with pytest.raises(AssertionError, match="Regression #1632"):
            assert_probes_invariant(valid_backend_workload)

    def test_regression_missing_probes_fails(self, valid_backend_workload):
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        del backend_container["readinessProbe"]
        with pytest.raises(AssertionError, match="missing readinessProbe"):
            assert_probes_invariant(valid_backend_workload)

    def test_regression_1633_missing_container_security_context_fails(
        self, valid_backend_workload
    ):
        """Regression #1633: missing security context on worker/backend."""
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        del backend_container["securityContext"]

        with pytest.raises(AssertionError, match="Regression #1633"):
            assert_security_context_invariant(
                valid_backend_workload["pod_spec"], backend_container, "test"
            )

    def test_regression_1633_missing_pod_security_context_fails(
        self, valid_backend_workload
    ):
        del valid_backend_workload["pod_spec"]["securityContext"]
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )

        with pytest.raises(AssertionError, match="Regression #1633"):
            assert_security_context_invariant(
                valid_backend_workload["pod_spec"], backend_container, "test"
            )

    def test_regression_insecure_privilege_escalation_fails(
        self, valid_backend_workload
    ):
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        backend_container["securityContext"]["allowPrivilegeEscalation"] = True

        with pytest.raises(
            AssertionError, match="allowPrivilegeEscalation=false"
        ):
            assert_security_context_invariant(
                valid_backend_workload["pod_spec"], backend_container, "test"
            )

    def test_regression_run_as_root_fails(self, valid_backend_workload):
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        backend_container["securityContext"]["runAsNonRoot"] = False

        with pytest.raises(AssertionError, match="runAsNonRoot=true"):
            assert_security_context_invariant(
                valid_backend_workload["pod_spec"], backend_container, "test"
            )

    def test_regression_missing_resources_fails(self, valid_backend_workload):
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        del backend_container["resources"]

        with pytest.raises(AssertionError, match="missing 'resources'"):
            assert_resources_invariant(backend_container, "test")

    def test_regression_cpu_request_exceeds_limit_fails(
        self, valid_backend_workload
    ):
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        backend_container["resources"]["requests"]["cpu"] = "2000m"
        backend_container["resources"]["limits"]["cpu"] = "500m"

        with pytest.raises(AssertionError, match="cpu request .* exceeds limit"):
            assert_resources_invariant(backend_container, "test")

    def test_regression_missing_image_pull_policy_fails(
        self, valid_backend_workload
    ):
        backend_container = next(
            c
            for _, c in get_all_containers(valid_backend_workload["pod_spec"])
            if c["name"] == "backend"
        )
        del backend_container["imagePullPolicy"]

        with pytest.raises(AssertionError, match="missing imagePullPolicy"):
            assert_image_pull_policy_invariant(backend_container, "test")
