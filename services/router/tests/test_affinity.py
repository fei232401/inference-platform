from collections import Counter

import pytest

from src.admission import AdmissionController
from src.affinity import affinity_key, bounded_choice, rendezvous_order


def backends(*ids, inflight=None):
    inflight = inflight or {}
    return [{"backend_id": i, "score": 1, "excluded": False, "inflight": inflight.get(i, 0)} for i in ids]


def test_key_uses_only_the_configured_prefix():
    assert affinity_key("shared document" + "question A", 15) == affinity_key("shared document" + "question B", 15)
    assert affinity_key("shared document A", 17) != affinity_key("shared document B", 17)


def test_same_key_prefers_same_backend_and_keys_spread():
    eligible = backends(1, 2, 3)
    assert {rendezvous_order("k", eligible)[0]["backend_id"] for _ in range(5)} == {rendezvous_order("k", eligible)[0]["backend_id"]}
    counts = Counter(rendezvous_order(f"key-{n}", eligible)[0]["backend_id"] for n in range(600))
    assert set(counts) == {1, 2, 3} and min(counts.values()) > 120


def test_removing_a_backend_only_moves_its_own_keys():
    before = {n: rendezvous_order(f"key-{n}", backends(1, 2, 3))[0]["backend_id"] for n in range(300)}
    after = {n: rendezvous_order(f"key-{n}", backends(1, 2))[0]["backend_id"] for n in range(300)}
    assert all(after[n] == before[n] for n in before if before[n] != 3)


def test_bounded_load_spills_to_next_preference():
    key = "hot-prefix"
    preferred = rendezvous_order(key, backends(1, 2))[0]["backend_id"]
    other = 2 if preferred == 1 else 1
    chosen, info = bounded_choice(key, backends(1, 2, inflight={preferred: 3, other: 0}), 1.25)
    assert info["load_bound"] == 3
    assert chosen["backend_id"] == other and info["rank"] == 1 and info["preferred_id"] == preferred
    chosen, info = bounded_choice(key, backends(1, 2, inflight={preferred: 2, other: 1}), 1.25)
    assert chosen["backend_id"] == preferred and info["rank"] == 0


def test_reservation_tracks_inflight_and_reports_affinity():
    controller = AdmissionController()
    candidates = [{"backend_id": 1, "score": 1, "excluded": False}, {"backend_id": 2, "score": 1, "excluded": False}]
    with controller.reserve(candidates, "prefix_affinity", 4, {}, "doc") as first:
        with controller.reserve(candidates, "prefix_affinity", 4, {}, "doc") as second:
            assert first.chosen["backend_id"] == second.chosen["backend_id"]
            assert second.chosen["inflight"] == 1 and second.affinity["rank"] == 0


def test_affinity_policy_requires_a_key():
    with pytest.raises(ValueError):
        with AdmissionController().reserve([{"backend_id": 1, "score": 1, "excluded": False}], "prefix_affinity", 4, {}):
            pass
