import random
from collections import Counter
from types import SimpleNamespace

from api.endpoints.challenge import _payload_manager as pm_module
from api.endpoints.challenge._payload_manager import build_run_schedule

FRAMEWORKS = ["seleniumbase", "nodriver", "pydoll", "patchright"]
SERVERS = [
    {"url": "http://runner-1:8080", "device_type": "linux"},
    {"url": "http://runner-2:8080", "device_type": "mac"},
]


def _dummy_config(frameworks, *, headed, headless, human_count, shuffle):
    return SimpleNamespace(
        challenge=SimpleNamespace(
            framework_images=[SimpleNamespace(name=name) for name in frameworks],
            human_count=human_count,
            bot_runner=SimpleNamespace(
                servers=[SimpleNamespace(**server) for server in SERVERS],
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
        FRAMEWORKS,
        SERVERS,
        headed_count=3,
        headless_count=2,
        human_count=1,
        shuffle=False,
    )

    assert len(schedule) == len(FRAMEWORKS) * 5 * len(SERVERS) + 1
    by_name = Counter(unit["name"] for unit in schedule)
    for framework in FRAMEWORKS:
        assert by_name[framework] == 5 * len(SERVERS)
    assert by_name["human"] == 1


def test_mode_split_per_framework():
    schedule = build_run_schedule(
        FRAMEWORKS,
        SERVERS,
        headed_count=3,
        headless_count=2,
        human_count=0,
        shuffle=False,
    )

    for framework in FRAMEWORKS:
        assert _mode_counts(schedule, framework) == (6, 4)
    assert all(unit["name"] != "human" for unit in schedule)


def test_human_units_carry_no_mode():
    schedule = build_run_schedule(
        FRAMEWORKS,
        SERVERS,
        headed_count=1,
        headless_count=1,
        human_count=2,
        shuffle=False,
    )

    humans = [unit for unit in schedule if unit["name"] == "human"]
    assert len(humans) == 2
    assert all(unit["headless"] is None for unit in humans)
    assert all(unit["server_url"] is None for unit in humans)
    assert all(unit["device_type"] is None for unit in humans)


def test_deterministic_order_when_not_shuffled():
    schedule = build_run_schedule(
        ["a", "b"],
        SERVERS,
        headed_count=1,
        headless_count=1,
        human_count=0,
        shuffle=False,
    )

    assert [
        (
            unit["name"],
            unit["headless"],
            unit["server_url"],
            unit["device_type"],
        )
        for unit in schedule
    ] == [
        ("a", False, SERVERS[0]["url"], "linux"),
        ("a", True, SERVERS[0]["url"], "linux"),
        ("a", False, SERVERS[1]["url"], "mac"),
        ("a", True, SERVERS[1]["url"], "mac"),
        ("b", False, SERVERS[0]["url"], "linux"),
        ("b", True, SERVERS[0]["url"], "linux"),
        ("b", False, SERVERS[1]["url"], "mac"),
        ("b", True, SERVERS[1]["url"], "mac"),
    ]


def test_shuffle_preserves_counts_and_modes():
    random.seed(7)
    schedule = build_run_schedule(
        FRAMEWORKS,
        SERVERS,
        headed_count=3,
        headless_count=2,
        human_count=1,
        shuffle=True,
    )

    by_name = Counter(unit["name"] for unit in schedule)
    for framework in FRAMEWORKS:
        assert by_name[framework] == 10
        assert _mode_counts(schedule, framework) == (6, 4)
    assert by_name["human"] == 1


def test_shuffle_is_randomized_between_runs():
    random.seed(1)
    first = [
        (unit["name"], unit["headless"])
        for unit in build_run_schedule(
            FRAMEWORKS,
            SERVERS,
            headed_count=3,
            headless_count=2,
            human_count=1,
            shuffle=True,
        )
    ]
    second = [
        (unit["name"], unit["headless"])
        for unit in build_run_schedule(
            FRAMEWORKS,
            SERVERS,
            headed_count=3,
            headless_count=2,
            human_count=1,
            shuffle=True,
        )
    ]
    assert first != second


def test_order_numbers_are_assignable_contiguously():
    schedule = build_run_schedule(
        FRAMEWORKS,
        SERVERS,
        headed_count=2,
        headless_count=2,
        human_count=1,
        shuffle=True,
    )
    # Every unit must expose the fields the payload manager needs to build a task.
    for unit in schedule:
        assert set(unit.keys()) == {
            "name",
            "headless",
            "server_url",
            "device_type",
        }


# --- PayloadManager wiring: config -> generated task schedule ---------------


def test_payload_manager_wires_config_counts(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a", "b"], headed=2, headless=1, human_count=2, shuffle=False),
    )

    manager = pm_module.PayloadManager()

    # 2 frameworks * (2 + 1) * 2 servers + 2 human = 14 tasks
    assert len(manager.tasks) == 14
    names = [task["name"] for task in manager.tasks.values()]
    assert names.count("a") == 6
    assert names.count("b") == 6
    assert names.count("human") == 2
    # expected_order must mirror each task's name by order_number
    assert all(
        manager.expected_order[index] == manager.tasks[index]["name"]
        for index in manager.tasks
    )
    # order numbers are contiguous from zero
    assert sorted(manager.tasks.keys()) == list(range(14))


def test_payload_manager_deterministic_when_shuffle_off(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a", "b"], headed=1, headless=1, human_count=0, shuffle=False),
    )

    manager = pm_module.PayloadManager()

    assert [
        (
            task["name"],
            task["headless"],
            task["server_url"],
            task["device_type"],
        )
        for task in manager.tasks.values()
    ] == [
        ("a", False, SERVERS[0]["url"], "linux"),
        ("a", True, SERVERS[0]["url"], "linux"),
        ("a", False, SERVERS[1]["url"], "mac"),
        ("a", True, SERVERS[1]["url"], "mac"),
        ("b", False, SERVERS[0]["url"], "linux"),
        ("b", True, SERVERS[0]["url"], "linux"),
        ("b", False, SERVERS[1]["url"], "mac"),
        ("b", True, SERVERS[1]["url"], "mac"),
    ]


def test_payload_manager_respects_human_count_zero(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a"], headed=1, headless=1, human_count=0, shuffle=True),
    )

    manager = pm_module.PayloadManager()

    assert len(manager.tasks) == 4
    assert all(task["name"] != "human" for task in manager.tasks.values())


def test_payloads_from_multiple_servers_are_scored_independently(monkeypatch):
    monkeypatch.setattr(
        pm_module,
        "config",
        _dummy_config(["a"], headed=1, headless=0, human_count=0, shuffle=False),
    )
    manager = pm_module.PayloadManager()

    manager.submit_task(
        framework_names=["a"],
        payload={"order_number": 0},
        headless_non_ua=False,
    )
    assert manager.calculate_score() == 0.5

    manager.submit_task(
        framework_names=["a"],
        payload={"order_number": 1},
        headless_non_ua=False,
    )

    assert len(manager.submitted_payloads) == 2
    assert manager.submitted_payloads[0]["server_url"] == SERVERS[0]["url"]
    assert manager.submitted_payloads[0]["device_type"] == "linux"
    assert manager.submitted_payloads[1]["server_url"] == SERVERS[1]["url"]
    assert manager.submitted_payloads[1]["device_type"] == "mac"
    assert manager.calculate_score() == 1.0
