# 07 — Practice environment (Community Edition)

Location: `practice/ai-league-community-edition/` (cloned from github.com/aws-ai-community/ai-league-community-edition).

## Prereqs [verified: README]
AWS account with AdministratorAccess; Node 22+; Python 3.12+; AWS CLI configured; `npm i -g aws-cdk`; Docker; Bedrock model access/service quota for Nova Lite / Claude Haiku. **Region: us-east-1 only.**

## Deploy
```
cd practice/ai-league-community-edition
npm install
npx cdk bootstrap aws://<ACCOUNT_ID>/us-east-1     # once
CDK_DEFAULT_REGION=us-east-1 npx cdk deploy
```
Outputs: `UserInterfaceDomainName` (app URL), `AdminPassword` (first deploy). Login: `admin@aileague.community` + that password.
Teardown: `CDK_DEFAULT_REGION=us-east-1 npx cdk destroy` (removes everything including Bedrock deployments).

## Using it
- Pages: Map Builder, Gameplay (enter navigation prompt, watch replay + score breakdown), Leaderboard, Submission History, Configuration (model per purpose), Agent Builder (supervisor/sub-agents/tools/memory/guardrail), Fine-Tuning.
- Agent config as code: edit `agent-config/config.yaml`, then `npm run seed-config -- --profile <profile>` (`--dry-run` first). Wipes and re-creates the user's agent config.
- Tests: `npm test`; `cd lambda/agentic-api && python3 -m pytest tests/ -v`.

## Costs [verified: estimated-costs.md]
- Idle ~$0.50–$2/month (mostly CloudWatch logs). Per game ~$0.15–$0.70 (Nova 2 Lite $0.15–0.40; Haiku 4.5 $0.50–1.50, not credit-covered).
- Fine-tune $80/hour (see `06-fine-tuning.md`). SageMaker Code Editor $0.05/h if left running (auto-stops after 4 h idle).

## Local-only experiments (free)
- Copy `lambda/pathfinder-tool/index.py` locally to test path algorithms and generate training data without AWS.
- Clone `ai-league-competition-data` into `practice/` for real maps; import `map.json` into Map Builder.
