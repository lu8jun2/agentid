"""CLI entry point: python -m agentid <command>"""
import argparse
import json
import os
import sys


def main():
    parser = argparse.ArgumentParser(prog="agentid", description="AgentID CLI")
    sub = parser.add_subparsers(dest="command")

    # register
    reg = sub.add_parser("register", help="Register a new agent")
    reg.add_argument("--name", required=True)
    reg.add_argument("--type", dest="agent_type", default="custom")
    reg.add_argument("--owner-id", required=True)

    # event
    ev = sub.add_parser("event", help="Record an event")
    ev.add_argument("--type", dest="event_type", required=True)
    ev.add_argument("--payload", default="{}")

    # score
    sc = sub.add_parser("score", help="Query reputation score")
    sc.add_argument("--did", default=None)

    # leaderboard
    lb = sub.add_parser("leaderboard", help="Show leaderboard")
    lb.add_argument("--domain", default=None)
    lb.add_argument("--limit", type=int, default=20)

    # rate
    rt = sub.add_parser("rate", help="Submit peer rating")
    rt.add_argument("--target", required=True)
    rt.add_argument("--score", type=float, required=True)
    rt.add_argument("--domain", default="")
    rt.add_argument("--comment", default="")

    # verify
    sub.add_parser("verify", help="Verify event chain integrity")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    api_url = os.getenv("AGENTID_API_URL", "https://api.agentid.dev")
    api_key = os.getenv("AGENTID_API_KEY", "")
    did = os.getenv("AGENTID_DID", "")
    key_path = os.path.expanduser(os.getenv("AGENTID_OWNER_KEY_PATH", "~/.agentid/owner.pem"))

    if args.command == "register":
        import httpx
        resp = httpx.post(f"{api_url}/v1/agents", json={
            "name": args.name, "agent_type": args.agent_type, "owner_id": args.owner_id
        })
        resp.raise_for_status()
        data = resp.json()
        print(json.dumps(data, indent=2))
        print("\n⚠  Save the private_key above to ~/.agentid/owner.pem — shown only once.")
        return

    # All other commands need credentials
    if not api_key or not did:
        print("Set AGENTID_API_KEY and AGENTID_DID environment variables.")
        sys.exit(1)

    owner_key = open(key_path).read() if os.path.exists(key_path) else ""

    sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
    from sdk.client import AgentIDClient
    client = AgentIDClient(did, api_key, owner_key, base_url=api_url)

    if args.command == "event":
        result = client._post_event(args.event_type, json.loads(args.payload))
        print(json.dumps(result, indent=2))

    elif args.command == "score":
        result = client.get_score(args.did)
        s = result["score"]
        print(f"\n  {result.get('name', result['did'])}")
        print(f"  Score: {'★' * int(s)}{' ' * (10 - int(s))} {s}/10")
        if result.get("domain_scores"):
            print("\n  Domain scores:")
            for domain, ds in result["domain_scores"].items():
                print(f"    {domain:20s} {ds}/10")

    elif args.command == "leaderboard":
        rows = client.leaderboard(args.domain, args.limit)
        print(f"\n  {'#':>3}  {'Score':>5}  {'Name':<30}  {'Type'}")
        print("  " + "-" * 60)
        for r in rows:
            score_field = r.get("domain_score", r.get("score", 0))
            print(f"  {r['rank']:>3}  {score_field:>5.1f}  {r['name']:<30}  {r['agent_type']}")

    elif args.command == "rate":
        result = client.submit_peer_rating(args.target, args.score, args.comment, args.domain)
        print(json.dumps(result, indent=2))

    elif args.command == "verify":
        result = client.verify_chain()
        status = "✓ Valid" if result["valid"] else f"✗ Broken at event {result['broken_event_id']}"
        print(f"\n  Chain integrity: {status}")
        print(f"  Events verified: {result['event_count']}")


if __name__ == "__main__":
    main()
