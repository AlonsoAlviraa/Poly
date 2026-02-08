---
name: brainstorming-ideas
description: Explores user intent, requirements, and design before implementation. Use this to turn raw ideas into fully formed designs and specs through collaborative dialogue.
---

# Brainstorming Ideas Into Designs

## When to use this skill
- Before creating features, building components, or adding functionality.
- When the user has a vague idea that needs refining.
- When you need to understand purpose, constraints, and success criteria before coding.

## Workflow

### 1. Understand the Idea
- **Context Check**: Read current project state (files, docs, recent commits) first.
- **Refinement Loop**:
  - Ask **one question at a time**.
  - Prefer **multiple choice** questions to reduce user friction.
  - Focus on purpose, constraints, and success criteria.
  - *Stop when you can confidently propose a design.*

### 2. Explore Approaches
- Propose **2-3 different approaches** with trade-offs.
- Explain your reasoning and recommended option.
- Wait for user selection/feedback.

### 3. Present the Design
- **Incremental Presentation**: Break the design into small sections (200-300 words).
- **Validation Checkpoints**: After each section, ask: *"Does this look right so far?"*
- **Content**: Cover architecture, components, data flow, error handling, and testing.
- **YAGNI**: Ruthlessly remove unnecessary features.

### 4. Finalize & Document
- **Save**: Write the validated design to `docs/plans/YYYY-MM-DD-<topic>-design.md`.
- **Handoff**: Ask if the user is ready to set up for implementation (e.g., using `creating-implementation-plans`).

## Instructions
- **One question per message**: Never overwhelm the user.
- **Incremental validation**: Do not dump a massive design document all at once.
- **Flexibility**: Be ready to go back and rewrite sections if the user clarifies requirements.
