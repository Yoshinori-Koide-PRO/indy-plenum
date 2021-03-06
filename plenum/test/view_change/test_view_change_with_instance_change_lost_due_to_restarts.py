import pytest

from plenum.test.helper import freshness, waitForViewChange
from plenum.test.node_request.helper import sdk_ensure_pool_functional
from plenum.test.restart.helper import restart_nodes
from plenum.test.test_node import ensureElectionsDone
from stp_core.loop.eventually import eventually

FRESHNESS_TIMEOUT = 20


@pytest.fixture(scope="module")
def tconf(tconf):
    with freshness(tconf, enabled=True, timeout=FRESHNESS_TIMEOUT):
        yield tconf


def test_view_change_with_instance_change_lost_due_to_restarts(looper, txnPoolNodeSet,
                                                               sdk_pool_handle,
                                                               sdk_wallet_client,
                                                               tconf, tdir, allPluginsPath):
    """
    1. some_nodes (Beta and Gamma) send InstanceChange for all nodes.
    2. Restart other_nodes (Gamma and Delta)
    3. last_node (Delta) send InstanceChange for all nodes.
    4. Ensure elections done and pool is functional
    """
    current_view_no = txnPoolNodeSet[0].viewNo
    some_nodes = txnPoolNodeSet[1:3]
    other_nodes = txnPoolNodeSet[2:4]

    for n in some_nodes:
        n.view_changer.on_master_degradation()

    def check_ic_delivery():
        for node in txnPoolNodeSet:
            assert node.view_changer.instanceChanges._votes_count(current_view_no + 1) == 2
    looper.run(eventually(check_ic_delivery))

    restart_nodes(looper, txnPoolNodeSet, other_nodes, tconf, tdir, allPluginsPath, start_one_by_one=False)

    last_node = txnPoolNodeSet[-1]
    last_node.view_changer.on_master_degradation()
    waitForViewChange(looper, txnPoolNodeSet, current_view_no + 1, customTimeout=3 * FRESHNESS_TIMEOUT)

    ensureElectionsDone(looper, txnPoolNodeSet)
    sdk_ensure_pool_functional(looper, txnPoolNodeSet, sdk_wallet_client, sdk_pool_handle)
