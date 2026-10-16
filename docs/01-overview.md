# 01 — Overview

## What it is
AWS AI League: competition program with leaderboards and timed challenges that teaches AWS AI services. [web]
Agentic challenge = game "Dungeons of Agentic Interactions": your agent finds a path through a grid maze to a treasure chest, avoiding spikes and facing challenge tiles. Built on **Amazon Bedrock AgentCore** (Strands Agents SDK). [web]

## Mechanics in one paragraph
You write a navigation prompt (and configure supervisor/sub-agents/tools). The agent returns a path (list of up/down/left/right). The game engine walks the path: coins give points, spikes cost lives, challenge tiles ask a question the agent must answer (wrong = lose a life; 3 lives in 2025 finals, 5 is the CE default). Score also rewards lives left, reaching treasure, and using few tokens. See `02-scoring.md`.

## Formats seen
- **2025 finals:** finalists could only influence a pre-built agent via a startup runtime prompt (45 s to write), then 4–5 min to complete the maze; 3 rounds, round 3 added a boss before the treasure needing multiple subagents/tools. [web]
- **2026 Virtual League:** Aug 24–Oct 30 2026, fully virtual, AWS Builder ID required. Tracks: (1) agent on Bedrock AgentCore, (2) fine-tune model with SageMaker AI and Forge, (3) Agentic Football Cup. Regions APJ/EMEA/GCR/LATAM/NAMER each get one week per track (Mon–Fri); top scorer → regional finale Friday → winner gets trip to re:Invent 2026 Grand Finale. [web]
- **Summits:** one-afternoon format (build, iterate on live leaderboard, finale). Past maps: London, Bengaluru, NYC (dual door/key pairs), Hero Community Builder (10x10, 230 s), Virtual APJ (per-round point overrides), EMEA (reduced lives), GCR (no DQs). [web]

## This player's event
- Company event ~Oct 10 2026 (confirm). Includes fine-tuning. Real format/rules not yet confirmed — ask organizer (`09-todo-and-questions.md`).

## Links
- Community Edition: https://github.com/aws-ai-community/ai-league-community-edition
- Past maps/data: https://github.com/aws-ai-community/ai-league-competition-data
- 2025 finals writeup: https://builder.aws.com/content/36KAiofgazTuOH4StPlyIXpczJV/aws-ai-league-2025-finals
- AWS blog: https://aws.amazon.com/blogs/machine-learning/aws-ai-league-model-customization-and-agentic-showdown/
- Community Discord: https://discord.com/invite/FrEUMsZrAZ
