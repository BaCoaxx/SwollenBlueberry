from gwmultilaunch.presence import ProcInfo, command_matches_client, matching_pids, process_counts_as_online


def test_zombie_is_offline_with_or_without_a_window():
    assert process_counts_as_online("zombie", has_window=False) is False
    assert process_counts_as_online("zombie", has_window=True) is False
    assert process_counts_as_online("zombie", has_window=None) is False
    assert process_counts_as_online("dead", has_window=None) is False
    assert process_counts_as_online("running", has_window=None) is True
    assert process_counts_as_online("sleeping", has_window=False) is True

    zombie = ProcInfo(pid=5, cmdline=("/opt/gw/Gw.exe",), status="zombie", cwd="/opt/gw")
    assert (
        matching_pids(
            gwpath="/opt/gw/Gw.exe",
            root_pids={5},
            processes=[zombie],
            window_pids=set(),
        )
        == set()
    )


def test_path_match_distinguishes_install_folders_and_wine_z_drive():
    other = ProcInfo(pid=8, cmdline=("Gw.exe",), status="running", cwd="/opt/other")
    assert (
        matching_pids(gwpath="/opt/gw/Gw.exe", root_pids=set(), processes=[other], window_pids=None)
        == set()
    )
    same = ProcInfo(pid=8, cmdline=("Gw.exe",), status="running", cwd="/opt/gw")
    assert matching_pids(gwpath="/opt/gw/Gw.exe", root_pids=set(), processes=[same], window_pids=None) == {8}

    wine = ProcInfo(
        pid=7,
        cmdline=("wine", r"Z:\opt\gw\Gw.exe", "-email", "a@b.c"),
        status="sleeping",
        cwd="/opt/gw",
    )
    assert command_matches_client(wine.cmdline, None, wine.cwd, "/opt/gw/Gw.exe")
    assert matching_pids(gwpath="/opt/gw/Gw.exe", root_pids=set(), processes=[wine], window_pids=None) == {7}

    protected = ProcInfo(pid=3, cmdline=("/opt/gw/Gw.exe",), status="running", cwd="/opt/gw")
    assert (
        matching_pids(
            gwpath="/opt/gw/Gw.exe",
            root_pids=set(),
            processes=[protected],
            window_pids=None,
            protected_pids={3},
        )
        == set()
    )
