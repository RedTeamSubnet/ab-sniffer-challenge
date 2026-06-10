import random
from collections import Counter
from types import SimpleNamespace

from api.endpoints.challenge import _payload_manager as pm_module
from api.endpoints.challenge._payload_manager import build_run_schedule

FRAMEWORKS = ["seleniumbase", "nodriver", "pydoll", "patchright"]


def _dummy_config(frameworks, *, headed, headless, human_count, shuffle):
    return SimpleNamespace(
        challenge=SimpleNamespace(
            framework_images=[SimpleNamespace(name=name) for name in frameworks],
            human_count=human_count,
            bot_runner=SimpleNamespace(
                run_counts=SimpleNamespace(headed=headed, headless=headless),
                shuffle_runs=shuffle,
            ),
        )
    )


def _mode_counts(schedule, name):
    modes = [unit["headless"] for unit in schedule if unit["name"] == name]
    return modes.count(False), modes.count(True)


def test_total_and_per_framework_counts():
    schedule = build_run_schedule(
        FRAMEWORKS, headed_count=3, headless_count=2, human_count=1, shuffle=False
    )

    assert len(schedule) == len(FRAMEWORKS) * 5 + 1
    by_name = Counter(unit["name"] for unit in schedule)
    for framework in FRAMEWORKS:
        assert by_name[framework] == 5
    assert by_name["human"] == 1


def test_mode_split_per_framework():
    schedule = build_run_schedule(
        FRAMEWORKS, headed_count=3, headless_count=2, human_count=0, shuffle=False
    )

    for framework in FRAMEWORKS:
        assert _mode_counts(schedule, framework) == (3, 2)
    assert all(unit["name"] != "human" for unit in schedule)


def test_human_units_carry_no_mode():
    schedule = build_run_schedule(
        FRAMEWORKS, headed_count=1, headless_count=1, human_count=2, shuffle=False
    )

    humans = [unit for unit in schedule if unit["name"] == "human"]
    assert len(humans) == 2
    assert all(unit["headless"] is None for unit in humans)


def test_deterministic_order_when_not_shuffled():
    schedule = build_run_schedule(
        ["a", "b"], headed_count=1, headless_count=1, human_count=0, shuffle=False
    )

    assert [(unit["name"], unit["headless"]) for unit in schedule] == [
        ("a", False),
        ("a", True),
        ("b", False),
        ("b", True),
    ]


def test_shuffle_never_places_same_framework_adjacent():
    random.seed(20260611)
    for _ in range(100):
        schedule = build_run_schedule(
            FRAMEWORKS,
            headed_count=3,
            headless_count=2,
            human_count=1,
            shuffle=True,
        )
        names = [unit["name"] for unit in schedule]
        for left, right in zip(names, names[1:]):
            assert left != right, f"adjacent duplicate {left!r} in {names}"


def test_shuffle_preserves_counts_and_modes():
    random.seed(7)
    schedule = build_run_schedule(
        FRAMEWORKS, headed_count=3, headless_count=2, human_count=1, shuffle=True
    )

    by_name = Counter(unit["name"] for unit in schedule)
    for framework in FRAMEWORKS:
        assert by_name[framework] == 5
        assert _mode_counts(schedule, framework) == (3, 2)
    assert by_name["human"] == 1


def test_shuffle_is_randomized_between_runs():
    random.seed(1)
    first = [
        (unit["name"], unit["headless"])
        for unit in build_run_schedule(
            FRAMEWORKS, headed_count=3, headless_count=2, human_count=1, shuffle=True
        )
    ]
    second = [
        (unit["name"], unit["headless"])
        for unit in build_run_schedule(
            FRAMEWORKS, headed_count=3, headless_count=2, human_count=1, shuffle=True
        )
    ]
    assert first != second


def test_order_numbers_are_assignable_contiguously():
    schedule = build_run_schedule(
        FRAMEWORKS, headed_count=2, headless_count=2, human_count=1, shuffle=True
    )
    # Every unit must expose the fields the payload manager needs to build a task.
    for unit in schedule:
        assert set(unit.keys()) == {"name", "headless"}


# --- PayloadManager wiring: config -> generated task schedule ---------------


def test_payload_manager_wires_config_counts(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a", "b"], headed=2, headless=1, human_count=2, shuffle=False),
    )

    manager = pm_module.PayloadManager()

    # 2 frameworks * (2 + 1) + 2 human = 8 tasks
    assert len(manager.tasks) == 8
    names = [task["name"] for task in manager.tasks.values()]
    assert names.count("a") == 3
    assert names.count("b") == 3
    assert names.count("human") == 2
    # expected_order must mirror each task's name by order_number
    assert all(
        manager.expected_order[index] == manager.tasks[index]["name"]
        for index in manager.tasks
    )
    # order numbers are contiguous from zero
    assert sorted(manager.tasks.keys()) == list(range(8))


def test_payload_manager_deterministic_when_shuffle_off(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a", "b"], headed=1, headless=1, human_count=0, shuffle=False),
    )

    manager = pm_module.PayloadManager()

    assert [(task["name"], task["headless"]) for task in manager.tasks.values()] == [
        ("a", False),
        ("a", True),
        ("b", False),
        ("b", True),
    ]


def test_payload_manager_respects_human_count_zero(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a"], headed=1, headless=1, human_count=0, shuffle=True),
    )

    manager = pm_module.PayloadManager()

    assert len(manager.tasks) == 2
    assert all(task["name"] != "human" for task in manager.tasks.values())
