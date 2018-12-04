import pytest

from plenum.test.helper import sdk_send_random_requests
from stp_core.loop.eventually import eventually
from plenum.common.messages.node_messages import Commit
from plenum.test.delayers import delay
from plenum.test.propagate.helper import recvdRequest, recvdPropagate, \
    sentPropagate, recvdPrepareForInstId, recvdCommitForInstId
from plenum.test.test_node import TestNode
from plenum.test.node_request.helper import sdk_ensure_pool_functional


howlong = 20
initial_ledger_size = 0


@pytest.fixture(scope="module")
def tconf(tconf):
    OUTDATED_REQS_CHECK_ENABLED_OLD = tconf.OUTDATED_REQS_CHECK_ENABLED
    OUTDATED_REQS_CHECK_INTERVAL_OLD = tconf.OUTDATED_REQS_CHECK_INTERVAL
    PROPAGATES_PHASE_REQ_TIMEOUT_OLD = tconf.PROPAGATES_PHASE_REQ_TIMEOUT
    ORDERING_PHASE_REQ_TIMEOUT_OLD = tconf.ORDERING_PHASE_REQ_TIMEOUT

    tconf.OUTDATED_REQS_CHECK_ENABLED = True
    tconf.OUTDATED_REQS_CHECK_INTERVAL = 1
    tconf.PROPAGATES_PHASE_REQ_TIMEOUT = 3600
    tconf.ORDERING_PHASE_REQ_TIMEOUT = 7
    yield tconf

    tconf.OUTDATED_REQS_CHECK_ENABLED = OUTDATED_REQS_CHECK_ENABLED_OLD
    tconf.OUTDATED_REQS_CHECK_INTERVAL = OUTDATED_REQS_CHECK_INTERVAL_OLD
    tconf.PROPAGATES_PHASE_REQ_TIMEOUT = PROPAGATES_PHASE_REQ_TIMEOUT_OLD
    tconf.ORDERING_PHASE_REQ_TIMEOUT = ORDERING_PHASE_REQ_TIMEOUT_OLD


@pytest.fixture()
def setup(txnPoolNodeSet, looper, sdk_pool_handle, sdk_wallet_client):
    global initial_ledger_size
    A, B, C, D = txnPoolNodeSet  # type: TestNode
    delay(Commit, frm=[B, C, D], to=A, howlong=howlong)
    initial_ledger_size = txnPoolNodeSet[0].domainLedger.size
    request_couple_json = sdk_send_random_requests(
        looper, sdk_pool_handle, sdk_wallet_client, 1)
    return request_couple_json


def test_req_drop_on_commit_phase_on_master_primary_and_then_ordered(
        tconf, setup, looper, txnPoolNodeSet,
        sdk_wallet_client, sdk_pool_handle):
    global initial_ledger_size
    A, B, C, D = txnPoolNodeSet  # type: TestNode

    def check_propagates():
        # A should have received a request from the client
        assert len(recvdRequest(A)) == 1
        # A should have received a PROPAGATEs
        assert len(recvdPropagate(A)) == 3
        # A should have sent a PROPAGATE
        assert len(sentPropagate(A)) == 1
        # A should have one request in the requests queue
        assert len(A.requests) == 1

    timeout = howlong - 2
    looper.run(eventually(check_propagates, retryWait=.5, timeout=timeout))

    def check_drop():
        # A should have not received Prepares and Commits for master instance
        assert len(recvdPrepareForInstId(A, 0)) == 3
        assert len(recvdCommitForInstId(A, 0)) == 0
        # Request object should be dropped by timeout
        assert len(A.requests) == 0

    timeout = tconf.ORDERING_PHASE_REQ_TIMEOUT + tconf.OUTDATED_REQS_CHECK_INTERVAL + 1
    looper.run(eventually(check_drop, retryWait=.5, timeout=timeout))

    for n in txnPoolNodeSet:
        n.nodeIbStasher.resetDelays()

    def check_commits_received():
        # A should have received all delayed Prepares and Commits for master instance
        assert len(recvdCommitForInstId(A, 0)) == 3

    timeout = howlong * 2
    looper.run(eventually(check_commits_received, retryWait=.5, timeout=timeout))

    def check_ledger_size():
        # The request should be eventually ordered
        for node in txnPoolNodeSet:
            assert node.domainLedger.size - initial_ledger_size == 1

    looper.run(eventually(check_ledger_size, retryWait=.5, timeout=timeout))

    sdk_ensure_pool_functional(looper, txnPoolNodeSet, sdk_wallet_client, sdk_pool_handle)
