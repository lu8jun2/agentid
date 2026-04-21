/**
 * OpenClaw AgentID adapter — Node.js thin wrapper over the AgentID HTTP API.
 * Place in ~/.openclaw/workspace/skills/ and add to TOOLS.md.
 *
 * Config (env or ~/.openclaw/workspace/AGENTS.md):
 *   AGENTID_API_KEY=aid_key_...
 *   AGENTID_DID=did:agentid:local:...
 *   AGENTID_OWNER_KEY_PATH=~/.agentid/owner.pem
 *   AGENTID_API_URL=https://api.agentid.dev
 */
const https = require("https");
const http = require("http");
const crypto = require("crypto");
const fs = require("fs");

const BASE_URL = process.env.AGENTID_API_URL || "https://api.agentid.dev";
const API_KEY = process.env.AGENTID_API_KEY || "";
const AGENT_DID = process.env.AGENTID_DID || "";
const OWNER_KEY_PATH = process.env.AGENTID_OWNER_KEY_PATH || "";

function _sign(privateKeyPem, data) {
  return crypto.sign(null, Buffer.from(data), { key: privateKeyPem, dsaEncoding: "ieee-p1363" }).toString("hex");
}

async function _post(path, body) {
  const bodyJson = JSON.stringify(body);
  const bodyHash = crypto.createHash("sha256").update(bodyJson).digest("hex");
  const ts = Date.now().toString();
  const ownerKey = fs.readFileSync(OWNER_KEY_PATH, "utf8");
  const sig = _sign(ownerKey, bodyHash);

  return new Promise((resolve, reject) => {
    const url = new URL(BASE_URL + path);
    const lib = url.protocol === "https:" ? https : http;
    const req = lib.request(url, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${API_KEY}`,
        "X-Owner-Signature": sig,
        "X-Timestamp": ts,
        "Content-Length": Buffer.byteLength(bodyJson),
      },
    }, (res) => {
      let data = "";
      res.on("data", (chunk) => data += chunk);
      res.on("end", () => resolve(JSON.parse(data)));
    });
    req.on("error", reject);
    req.write(bodyJson);
    req.end();
  });
}

const AgentID = {
  async recordTaskCompleted(taskId, taskType, durationMs, domain = "") {
    return _post("/v1/events", {
      agent_did: AGENT_DID, event_type: "TASK_COMPLETED",
      payload: { task_id: taskId, task_type: taskType, duration_ms: durationMs, domain },
    });
  },
  async recordTokensConsumed(tokens, model, taskId = "", domain = "") {
    return _post("/v1/events", {
      agent_did: AGENT_DID, event_type: "TOKEN_CONSUMED",
      payload: { tokens, model, task_id: taskId, domain },
    });
  },
  async recordProjectJoin(projectId, projectName, role = "participant") {
    return _post("/v1/events", {
      agent_did: AGENT_DID, event_type: "PROJECT_JOIN",
      payload: { project_id: projectId, project_name: projectName, role },
    });
  },
  async recordCollaboration(peerDid, collabType = "task") {
    return _post("/v1/events", {
      agent_did: AGENT_DID, event_type: "COLLABORATION_START",
      payload: { peer_did: peerDid, collab_type: collabType },
    });
  },
  async submitPeerRating(targetDid, score, comment = "", domain = "") {
    return _post("/v1/events", {
      agent_did: AGENT_DID, event_type: "PEER_RATING",
      payload: { target_did: targetDid, score, comment, domain },
    });
  },
};

module.exports = AgentID;
