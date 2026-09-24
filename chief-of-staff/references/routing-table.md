# Routing table (machine-readable) - the executable source of truth for chief-of-staff dispatch.
# scripts/route.py parses THIS table. Rows are matched top-to-bottom; first hit wins (so order = priority).
# Format: | keywords (comma-separated, any match) | route | mode |
# modes: gate (stop+confirm Shai), direct (one specialist), team (multi), advisor (C-suite), clarify (ask one Q), triage (default).

| keywords | route | mode |
|---|---|---|
| money,payment,invoice,charge,card,transfer,refund,wire,bank,signup,purchase | STOP-confirm-with-shai | gate |
| review this code,code review,review code,audit this code,pull request,refactor,lint | code-reviewer | direct |
| security,vuln,pentest,secret,exploit,owasp,breach,backdoor | security-auditor | direct |
| qa,test plan,test cases,quality check,regression test | qa-engineer | direct |
| contract,nda,legal,terms,liability,gdpr,dpa,compliance | legal-advisor | direct |
| slow,latency,perf,performance,load test,n+1,bottleneck | performance-engineer | direct |
| seo,aso,ranking,serp,keyword,app store optimization | seo-aso-specialist | direct |
| down,outage,incident,broken in prod,500 error,site is down | site-reliability-engineer | direct |
| design,ui,ux,layout,wireframe,figma,mockup | ui-ux-designer | direct |
| migrate,upgrade php,upgrade laravel,version bump,framework migration | codebase-migration-plan | direct |
| what have we learned,pattern across,synthesize learnings | knowledge-synthesizer | direct |
| what's new,latest,trending,find a tool,new tool,we don't know how | talent-scout | direct |
| build me,new feature,new screen,build a,build an,landing page,ship a product | cto+full-stack-developer+ui-ux-designer+qa-engineer | team |
| write me,content,blog post,copy,newsletter,social post | cmo+content-marketer | team |
| decide between,should we choose,which option,vs,trade-off | c-suite-advisor | advisor |
| i don't know,not sure what,help me figure out | clarify-one-question | clarify |
