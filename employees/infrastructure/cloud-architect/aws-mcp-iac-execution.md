# AWS MCP - IaC validation + safe provisioning patterns

Absorbed from awslabs/mcp (Apache-2.0, ~9.3k stars, monorepo of AWS-official MCP servers; commit main @ 2026-06-13). Net-new layer the architect lacked: a live IaC **validation + provisioning execution** discipline on top of its existing design/decision-matrix doctrine. Architect still designs; this is the pre-handoff template-validation gate and the guardrailed live-provisioning workflow it imposes on whoever executes.

## When to use
- Reviewing/validating a CloudFormation or CDK template BEFORE it goes to devops-engineer or to deploy.
- Standing up scratch/sandbox resources to validate an architecture decision (declarative, via Cloud Control API).
- Pricing a design before committing (see aws-pricing-mcp-server).

## Template validation gate (aws-iac-mcp-server) - run BEFORE any deploy
1. **Syntax + schema** - validate with `cfn-lint`; catch invalid properties/schema violations; expect specific fix suggestions WITH line numbers (don't accept a vague "invalid").
2. **Security/compliance** - validate with `cfn-guard` against the AWS Guard Rules Registry + Control Tower proactive controls. CDK templates: require CDK-NAG checks. A template that hasn't passed cfn-guard is not handover-ready.
3. **Deployment failure analysis** - on a failed stack, pattern-match against the 30+ known CloudFormation failure cases and follow the CloudTrail deep link to root cause instead of guessing.
4. Doc grounding - resolve resource types/properties against official CloudFormation + CDK docs (read_iac_documentation_page) rather than recalling property names; CFN/CDK property names hallucinate easily.

## Safe live-provisioning workflow (Cloud Control API / ccapi pattern)
Cloud Control API can declaratively create/read/update/delete/list 1,100+ resource types. When provisioning live, enforce this token-chained sequence - each step must complete before the next, server-side, with no agent bypass:
1. Check credentials; surface the **account ID + region** to the human first.
2. Generate the config + CloudFormation template for what will be created.
3. **explain()** - show the human exactly what will be created/modified. Informed consent before execution, always.
4. Run a security scan against the template (SECURITY_SCANNING=enabled by default).
5. Only if scans pass (or are explicitly disabled with a logged warning) → create/update.
6. Auto-apply default management tags for tracking/audit.
7. Validate the resource actually came up; summarize, surfacing any security warnings.
8. Optionally emit an IaC template aligned to what was created (so live resources stay codified, never drift into click-ops).

Doctrine: the security gate is non-bypassable. Never create resources without the explain step and a passing (or consciously waived) scan. Note: the standalone ccapi-mcp-server is deprecated upstream in favor of aws-iac-mcp-server; the secure-workflow doctrine above is the durable, portable part - keep it regardless of which server hosts it.

## Serverless design help (aws-serverless-mcp-server)
For SAM/Lambda designs: read-only by default, controlled access to sensitive data; SAM lifecycle (init/build/deploy/local-test); event-source schemas + EventBridge schema registry for type-safe handlers; sample SAM templates from Serverless Land per app type. Use it to pressure-test function boundaries, event sources, and service integrations before recommending serverless over containers.

## CONNECT note (host installs)
These are MCP servers the architect uses, not absorbed code. Host installs per server via `uvx awslabs.<server>@latest` (Python 3.10+, uv, AWS CLI/SAM CLI, valid AWS creds). Relevant servers: aws-iac-mcp-server, aws-serverless-mcp-server, aws-pricing-mcp-server, aws-api-mcp-server. Live cloud execution requires scoped IAM - least-privilege role, never long-lived root keys.
