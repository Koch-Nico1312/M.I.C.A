# Obsidian Vault Integration Guide

This guide explains how to set up and use Obsidian Vault integration for M.I.C.A memory.

## Overview

The Obsidian Vault integration allows M.I.C.A to:
- Save each conversation as a separate note in your Obsidian vault
- Automatically link related notes using AI
- Create person and project notes
- Search through your knowledge base
- Build a personal knowledge graph over time

## Prerequisites

1. [Obsidian](https://obsidian.md/) installed on your computer
2. An Obsidian vault (or create a new one)
3. M.I.C.A with Obsidian dependencies installed

## Step 1: Configure Obsidian Vault Path

1. Create or identify your Obsidian vault location
2. Configure M.I.C.A to use this vault:

**Option A: Using .env file**
```bash
# Edit .env
OBSIDIAN_ENABLED=true
OBSIDIAN_VAULT_PATH=~/Obsidian/M.I.C.A
```

**Option B: Using config.yaml**
```yaml
obsidian:
  enabled: true
  vault_path: "~/Obsidian/M.I.C.A"
```

The vault path will be expanded automatically (e.g., `~` becomes your home directory).

## Step 2: Vault Structure

M.I.C.A will automatically create the following structure in your vault:

```
~/Obsidian/M.I.C.A/
├── Conversations/    # Conversation notes
├── People/          # Person profiles
├── Projects/        # Project notes
└── Topics/          # Topic notes
```

## Step 3: Enable Conversation Tracking

Conversation tracking can be started manually or automatically:

### Manual Tracking
Use voice commands:
```
"M.I.C.A, start tracking this conversation"
"M.I.C.A, end conversation tracking"
```

Or use the obsidian_manager tool:
```python
obsidian_manager({
    "action": "start_tracking",
    "user_input": "Discussing project timeline"
})
```

### Automatic Tracking
Conversations are automatically saved when:
- You say "shutdown" or "goodbye"
- The session ends normally

## Usage Examples

### Start Conversation Tracking
```
"M.I.C.A, start tracking this conversation about the marketing campaign"
```

### End and Save Conversation
```
"M.I.C.A, end conversation tracking"
```

### Search Notes
```
"M.I.C.A, search my Obsidian notes for marketing"
"M.I.C.A, find notes about project X"
```

### Create Person Note
```
"M.I.C.A, create a note for John Smith"
```

### Create Project Note
```
"M.I.C.A, create a project note for Website Redesign"
```

### Get All Notes
```
"M.I.C.A, list all my Obsidian notes"
```

## Note Format

### Conversation Notes

Each conversation is saved with:

```markdown
# 2024-05-17 23:30

---
created: 2024-05-17T23:30:00
type: conversation
tags:
  - conversation
---

## Summary
Discussion about marketing campaign timeline and deliverables.

## Key Points
- Launch date set for June 15
- Budget approved at $50,000
- Team meeting scheduled for next week

## Actions Taken
- open_app: Chrome
- web_search: marketing campaign best practices
- gmail_manager: send email to team

## User Input
We need to plan the marketing campaign launch for next month.

## AI Responses
> I'll help you plan the marketing campaign...
> Let me search for best practices...

## Related Notes
- [[Marketing Strategy 2024]]
- [[Project Timeline]]
```

### Person Notes

```markdown
# John Smith

---
created: 2024-05-17T23:30:00
type: person
tags:
  - person
---

## Information
- role: Marketing Manager
- email: john@example.com
- last_contacted: 2024-05-17

## Update 2024-05-17
- Discussed marketing campaign
- context: Planning launch for June 15
```

### Project Notes

```markdown
# Website Redesign

---
created: 2024-05-17T23:30:00
type: project
tags:
  - project
  - project/active
---

## Description
Complete redesign of company website with new branding.

## Goals
- [ ] Update visual design
- [ ] Improve mobile responsiveness
- [ ] Optimize page load times
- [ ] Add new features

## Tasks
- [ ] Create wireframes
- [ ] Design mockups
- [ ] Develop frontend
- [ ] Test and deploy

## Notes
- Budget: $15,000
- Timeline: 6 weeks
- Team: 3 developers
```

## AI-Powered Note Linking

At the end of each conversation, M.I.C.A uses AI to:
1. Extract keywords from the conversation
2. Search for related notes in your vault
3. Automatically add `[[WikiLinks]]` to related notes
4. Build connections between conversations over time

This creates a knowledge graph that grows with each conversation.

## Advanced Features

### Manual Note Creation

You can manually create notes using the obsidian_manager tool:

```python
# Create a person note
obsidian_manager({
    "action": "create_person_note",
    "name": "Alice Johnson",
    "information": {
        "role": "Designer",
        "email": "alice@example.com",
        "skills": ["UI/UX", "Figma"]
    }
})

# Create a project note
obsidian_manager({
    "action": "create_project_note",
    "name": "Mobile App",
    "information": {
        "description": "iOS and Android app development",
        "status": "planning",
        "goals": ["MVP release", "User testing"],
        "tasks": ["Design screens", "Develop backend"]
    }
})
```

### Search with Obsidian Syntax

M.I.C.A supports Obsidian's powerful search syntax:
- `[[link]]` - Find notes linking to this note
- `tag:#work` - Find notes with specific tags
- `path:Conversations/` - Search in specific folder
- `file:project` - Search in filenames

### Integration with Obsidian Features

Your notes work with all Obsidian features:
- **Graph View** - Visualize connections between notes
- **Backlinks** - See which notes reference each other
- **Tags** - Organize with tags
- **Properties** - Use YAML frontmatter for metadata
- **Plugins** - Works with most Obsidian plugins

## Workflow Examples

### Daily Standup Tracking

1. Start tracking: "M.I.C.A, start tracking daily standup"
2. Discuss tasks and progress
3. End tracking: "M.I.C.A, end conversation"
4. Note automatically saved with all actions and key points

### Project Meeting Notes

1. Start tracking with project name
2. M.I.C.A captures decisions, action items, participants
3. Creates person notes for new contacts
4. Links to existing project notes automatically

### Research Sessions

1. Start tracking research topic
2. M.I.C.A performs searches and summarizes findings
3. All sources and conclusions saved
4. Linked to related research notes

## Privacy and Security

- All notes stored locally in your Obsidian vault
- No data sent to external services (except for AI linking if enabled)
- You control what gets saved
- Notes can be encrypted with Obsidian plugins
- Git-friendly (can version control your vault)

## Troubleshooting

### "Vault path not found"
- Ensure the vault path is correct in config
- Check that the directory exists or can be created
- Verify path expansion (use `~` for home directory)

### "Notes not being saved"
- Check that OBSIDIAN_ENABLED is true
- Verify conversation tracking is started
- Check file permissions on vault directory

### "AI linking not working"
- This feature uses keyword matching by default
- For advanced AI linking, ensure Gemini API is configured
- Check that the vault has existing notes to link to

### "Obsidian not showing notes"
- Ensure you're opening the correct vault in Obsidian
- Try refreshing Obsidian (Ctrl+R)
- Check that notes are in the expected subdirectories

## Best Practices

1. **Start tracking early** - Begin tracking at the start of important conversations
2. **Use descriptive summaries** - When ending tracking, provide a clear summary
3. **Review regularly** - Check your Obsidian vault to see the knowledge graph grow
4. **Organize with tags** - Use consistent tags for better organization
5. **Link manually** - Add manual [[links]] when AI misses connections
6. **Backup your vault** - Use Git or Obsidian Sync for backup

## Integration with Other Features

The Obsidian integration works with other M.I.C.A features:

- **Memory System** - Extracted information can create person/project notes
- **Semantic Search** - Search across your entire vault with RAG
- **Proactive Suggestions** - M.I.C.A can suggest creating notes based on context
- **Cross-Device Handover** - Send note summaries to your phone

## Future Enhancements

Potential future additions:
- Direct Obsidian plugin for M.I.C.A
- Real-time note editing in Obsidian
- Advanced NLP for better note linking
- Template system for different note types
- Calendar integration for meeting notes
- Task management integration

## Support

For issues or questions:
- Check the Obsidian documentation
- Verify your vault path configuration
- Ensure M.I.C.A has write permissions
- Check the console logs for error messages

---

**Build your personal knowledge graph with M.I.C.A and Obsidian! 🧠**
