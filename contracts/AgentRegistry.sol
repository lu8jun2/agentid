// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

/// @title AgentID Registry — Phase 2 on-chain identity
/// @notice Immutable registry mapping DID → owner + pubkey hash
contract AgentRegistry {
    struct AgentRecord {
        string did;
        address owner;
        bytes32 pubKeyHash;   // keccak256 of Ed25519 public key bytes
        uint256 registeredAt;
        bool active;
    }

    mapping(string => AgentRecord) public agents;
    mapping(address => string[]) public ownerAgents;

    event AgentRegistered(string indexed did, address indexed owner, uint256 timestamp);
    event AgentDeactivated(string indexed did, address indexed owner);

    function registerAgent(string calldata did, bytes32 pubKeyHash) external {
        require(bytes(agents[did].did).length == 0, "DID already registered");
        agents[did] = AgentRecord(did, msg.sender, pubKeyHash, block.timestamp, true);
        ownerAgents[msg.sender].push(did);
        emit AgentRegistered(did, msg.sender, block.timestamp);
    }

    function deactivate(string calldata did) external {
        require(agents[did].owner == msg.sender, "Not owner");
        agents[did].active = false;
        emit AgentDeactivated(did, msg.sender);
    }

    function getAgent(string calldata did) external view returns (AgentRecord memory) {
        return agents[did];
    }
}
