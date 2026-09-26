# Routing probes (CODE-01 / CODE-06 / CODE-08)

One probe per employee plus edge probes. This file is the source of truth:
`tests/test_router.py` parses it and runs every probe against the intake engine.

Format: `- ASSIGN "probe text" -> solaris.<employee>` or
`- ESCALATE "probe text" -> <reason>`.

## Employee probes (61)

- ASSIGN "Create a game-ready 3D model of a treasure chest with PBR textures" -> solaris.3d-artist
- ASSIGN "Set up an n8n workflow to automate lead follow-up and CRM sync" -> solaris.ai-automation-engineer
- ASSIGN "Train a PyTorch classifier to detect defective parts on the line" -> solaris.ai-ml-engineer
- ASSIGN "Build a WebXR product viewer with hand tracking for Quest headsets" -> solaris.ar-vr-developer
- ASSIGN "Design a REST API with FastAPI, JWT auth, and Postgres" -> solaris.backend-developer
- ASSIGN "Write a Solidity smart contract for an ERC-20 staking vault" -> solaris.blockchain-developer
- ASSIGN "Run a requirements workshop and write the BRD with acceptance criteria" -> solaris.business-analyst
- ASSIGN "Help me prepare a Series A pitch deck and fundraising strategy" -> solaris.ceo
- ASSIGN "Build a three-statement financial model and calculate our runway" -> solaris.cfo
- ASSIGN "Design our AWS multi-region architecture with a disaster recovery plan" -> solaris.cloud-architect
- ASSIGN "Define our brand positioning and go-to-market strategy for launch" -> solaris.cmo
- ASSIGN "review this code" -> solaris.code-reviewer
- ASSIGN "Run a SOC 2 compliance gap analysis and collect the evidence" -> solaris.compliance-auditor
- ASSIGN "Write a blog post announcing our launch for the newsletter" -> solaris.content-marketer
- ASSIGN "Set up our OKR cadence and write SOPs for the support team" -> solaris.coo
- ASSIGN "Optimize the conversion rate on our pricing page before launch" -> solaris.cro-landing-designer
- ASSIGN "Score our tech debt and write an ADR for the microservices split" -> solaris.cto
- ASSIGN "Our biggest account is showing churn signals, build a save plan" -> solaris.customer-success
- ASSIGN "Build a Metabase dashboard tracking MRR, churn, and CAC" -> solaris.data-analyst
- ASSIGN "Build an Airflow ETL pipeline into Snowflake with dbt models" -> solaris.data-engineer
- ASSIGN "Design an A/B test and tell me if the result is statistically significant" -> solaris.data-scientist
- ASSIGN "This Postgres query is slow, add the right indexes and set up a read replica" -> solaris.database-administrator
- ASSIGN "Scope this new client engagement and lock the milestones in ClickUp" -> solaris.delivery-lead
- ASSIGN "Set up GitHub Actions CI/CD with Docker builds and Terraform deploys" -> solaris.devops-engineer
- ASSIGN "Set up a Shopify store with a custom Liquid theme" -> solaris.ecommerce-specialist
- ASSIGN "Write a 5-email welcome series for new trial signups" -> solaris.email-specialist
- ASSIGN "Design a 3D-printable bracket with tight tolerances and export a STEP file" -> solaris.engineering-design
- ASSIGN "Dispatch this render job to the fleet and check m1 status" -> solaris.fleet-dispatcher
- ASSIGN "Provision this Mac mini as a headless build machine for the fleet" -> solaris.fleet-provisioner
- ASSIGN "Build a React dashboard with Tailwind and shadcn components" -> solaris.frontend-developer
- ASSIGN "Build an MVP prototype, scaffold the full-stack project end to end" -> solaris.full-stack-developer
- ASSIGN "Design the core game mechanics and level progression for our RPG" -> solaris.game-designer
- ASSIGN "Design a logo for my coffee brand" -> solaris.image-generator
- ASSIGN "Write ESP32 firmware reading sensors over MQTT with deep sleep" -> solaris.iot-engineer
- ASSIGN "Our pods are CrashLoopBackOff, fix the probes and HPA config" -> solaris.kubernetes-specialist
- ASSIGN "Review this MSA and redline the liability clause" -> solaris.legal-advisor
- ASSIGN "Design a RAG agent with tool calling and guardrails" -> solaris.llm-agent-designer
- ASSIGN "Do a competitor teardown and size the TAM for our market" -> solaris.market-researcher
- ASSIGN "Build a native iOS and Android app with push notifications" -> solaris.mobile-developer
- ASSIGN "Segment the homelab with VLANs and set up WireGuard VPN" -> solaris.network-engineer
- ASSIGN "Write a cold email sequence for prospecting CTOs" -> solaris.outreach-specialist
- ASSIGN "Launch a Google Ads campaign and fix our ROAS" -> solaris.paid-ads-manager
- ASSIGN "Integrate Stripe Checkout with webhooks for subscriptions" -> solaris.payments-specialist
- ASSIGN "Our API p99 latency is too high, profile it and cut the bundle size" -> solaris.performance-engineer
- ASSIGN "Write a PRD and prioritize the backlog with RICE scoring" -> solaris.product-manager
- ASSIGN "Plan the next sprint in Jira and run the retrospective" -> solaris.project-manager
- ASSIGN "Onboard this new project with the full activation sequence" -> solaris.project-onboarding
- ASSIGN "Write an Upwork proposal for this web development job" -> solaris.proposal-writer
- ASSIGN "Write a test plan for the client portal login regression" -> solaris.qa-engineer
- ASSIGN "Prepare a technical demo and POC for the enterprise prospect" -> solaris.sales-engineer
- ASSIGN "Penetration test our web app for OWASP top 10 vulnerabilities" -> solaris.security-auditor
- ASSIGN "Improve our Google ranking with technical SEO and backlinks" -> solaris.seo-aso-specialist
- ASSIGN "Define SLOs and error budgets with proper on-call rotations" -> solaris.site-reliability-engineer
- ASSIGN "Plan our LinkedIn content calendar for next month" -> solaris.social-media-manager
- ASSIGN "Write API docs with an OpenAPI spec for our REST endpoints" -> solaris.technical-writer
- ASSIGN "Create a Figma design system with tokens and dark mode" -> solaris.ui-ux-designer
- ASSIGN "Fix this Unity C# script for player movement" -> solaris.unity-developer
- ASSIGN "Build a UE5 level with Blueprints and Niagara effects" -> solaris.unreal-developer
- ASSIGN "Edit this video with captions and export vertical for Reels" -> solaris.video-editor
- ASSIGN "Create a voiceover for our explainer with ElevenLabs" -> solaris.voice-audio-producer
- ASSIGN "Build a custom WordPress block theme with Gutenberg blocks" -> solaris.wordpress-master

## Edge probes

- ASSIGN "please review this python code for security issues" -> solaris.code-reviewer
- ASSIGN "Please optimize the conversion rate on our pricing page for the launch next week" -> solaris.cro-landing-designer
- ESCALATE "our production site is down and customers cannot check out" -> high_risk
- ESCALATE "my blood pressure is high what should I do" -> out_of_authority
- ASSIGN "Build a REST API and a marketing landing page for the client portal" -> solaris.full-stack-developer
