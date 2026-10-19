from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest

from src.admission import AdmissionController, AdmissionRejected


def candidates():
    return [{"backend_id": 1, "score": 1, "excluded": False}]


def test_capacity_rejection_and_release():
    controller = AdmissionController()
    with controller.reserve(candidates(), "least_inflight", 1, {}):
        with pytest.raises(AdmissionRejected, match="backend_capacity_exhausted"):
            with controller.reserve(candidates(), "least_inflight", 1, {}):
                pytest.fail("over capacity")
    with controller.reserve(candidates(), "least_inflight", 1, {}) as slot:
        assert slot.chosen["inflight"] == 0


def test_release_after_backend_exception():
    controller = AdmissionController()
    with pytest.raises(RuntimeError):
        with controller.reserve(candidates(), "least_inflight", 1, {}):
            raise RuntimeError("backend failed")
    with controller.reserve(candidates(), "least_inflight", 1, {}) as slot:
        assert slot.chosen["inflight"] == 0


def test_least_inflight_uses_current_reservations():
    controller = AdmissionController()
    with controller.reserve(candidates(), "least_inflight", 4, {}):
        ranked = candidates() + [{"backend_id": 2, "score": 0, "excluded": False}]
        with controller.reserve(ranked, "least_inflight", 4, {}) as slot:
            assert slot.chosen["backend_id"] == 2


def test_health_exclusion_and_override():
    controller = AdmissionController()
    with controller.reserve(candidates(), "least_inflight", 4, {"1": 1}):
        with pytest.raises(AdmissionRejected, match="backend_capacity_exhausted"):
            with controller.reserve(candidates(), "least_inflight", 4, {"1": 1}):
                pytest.fail("override ignored")
    with pytest.raises(AdmissionRejected, match="no_candidate"):
        with controller.reserve([{**candidates()[0], "excluded": True}], "least_inflight", 4, {}):
            pytest.fail("unhealthy admitted")


def test_concurrent_reservations_do_not_exceed_limit():
    controller = AdmissionController()
    gate = Barrier(8)
    release = Barrier(8)

    def attempt(_):
        gate.wait(timeout=5)
        try:
            with controller.reserve(candidates(), "least_inflight", 2, {}):
                release.wait(timeout=5)
                return True
        except AdmissionRejected:
            release.wait(timeout=5)
            return False

    with ThreadPoolExecutor(max_workers=8) as executor:
        assert sum(executor.map(attempt, range(8))) == 2
    with controller.reserve(candidates(), "least_inflight", 2, {}) as slot:
        assert slot.chosen["inflight"] == 0
