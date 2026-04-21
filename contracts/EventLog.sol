// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AgentID EventLog — Phase 2 on-chain event hash anchoring
/// @notice Stores event hashes on-chain; full payloads live on IPFS
contract EventLog {
    struct EventRecord {
        string agentDid;
        bytes32 eventHash;
        string ipfsCid;       // full payload pinned to IPFS
        uint256 timestamp;
    }

    mapping(bytes32 => EventRecord) public events;

    event EventAnchored(string indexed agentDid, bytes32 indexed eventHash, string ipfsCid);

    function anchorEvent(
        string calldata agentDid,
        bytes32 eventHash,
        string calldata ipfsCid
    ) external {
        require(events[eventHash].timestamp == 0, "Event already anchored");
        events[eventHash] = EventRecord(agentDid, eventHash, ipfsCid, block.timestamp);
        emit EventAnchored(agentDid, eventHash, ipfsCid);
    }

    function getEvent(bytes32 eventHash) external view returns (EventRecord memory) {
        return events[eventHash];
    }
}
