"""
Obsidian Vault Integration for JARVIS Memory
Stores conversations as notes and uses AI to link them together
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import re

from config.config_loader import get_config


@dataclass
class ConversationNote:
    """Represents a conversation note in Obsidian"""
    title: str
    content: str
    tags: List[str]
    created_at: datetime
    related_notes: List[str]
    metadata: Dict[str, Any]


class ObsidianVault:
    """Manages Obsidian vault operations"""
    
    def __init__(self):
        self.config = get_config()
        self.enabled = self.config.get('obsidian.enabled', False)
        vault_path_str = self.config.get('obsidian.vault_path', '~/Obsidian/Jarvis')
        
        try:
            self.vault_path = Path(vault_path_str).expanduser()
        except Exception as e:
            print(f"[Obsidian] ⚠️ Invalid vault path: {e}")
            self.vault_path = Path.home() / "Obsidian" / "Jarvis"
        
        # Create vault directory if it doesn't exist
        try:
            self.vault_path.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            print(f"[Obsidian] ⚠️ Could not create vault directory: {e}")
            self.enabled = False
            return
        
        # Subdirectories
        self.conversations_dir = self.vault_path / "Conversations"
        self.people_dir = self.vault_path / "People"
        self.projects_dir = self.vault_path / "Projects"
        self.topics_dir = self.vault_path / "Topics"
        
        for dir_path in [self.conversations_dir, self.people_dir, 
                        self.projects_dir, self.topics_dir]:
            try:
                dir_path.mkdir(exist_ok=True)
            except Exception as e:
                print(f"[Obsidian] ⚠️ Could not create directory {dir_path}: {e}")
        
        if self.enabled:
            print(f"[Obsidian] ✅ Vault initialized at {self.vault_path}")
    
    def create_conversation_note(self, conversation: Dict[str, Any], 
                               related_notes: List[str] = None) -> str:
        """Create a new conversation note"""
        if not self.enabled:
            return ""
        
        # Generate title
        timestamp = datetime.now()
        title = f"Conversation {timestamp.strftime('%Y-%m-%d %H-%M')}"
        
        # Build content
        content = self._build_note_content(conversation, timestamp)
        
        # Add related notes links
        if related_notes:
            content += "\n\n## Related Notes\n"
            for note in related_notes:
                content += f"- [[{note}]]\n"
        
        # Create file
        filename = f"{timestamp.strftime('%Y%m%d-%H%M%S')}.md"
        file_path = self.conversations_dir / filename
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[Obsidian] 📝 Created note: {filename}")
        return title
    
    def _build_note_content(self, conversation: Dict[str, Any], 
                          timestamp: datetime) -> str:
        """Build the content of a note"""
        content = f"# {timestamp.strftime('%Y-%m-%d %H:%M')}\n\n"
        
        # Add metadata (YAML frontmatter)
        content += "---\n"
        content += f"created: {timestamp.isoformat()}\n"
        content += f"type: conversation\n"
        
        if 'user_input' in conversation:
            content += f"user_input: {conversation['user_input'][:100]}...\n"
        
        content += "tags:\n"
        content += "  - conversation\n"
        content += "---\n\n"
        
        # Add conversation summary
        if 'summary' in conversation:
            content += f"## Summary\n{conversation['summary']}\n\n"
        
        # Add key points
        if 'key_points' in conversation:
            content += "## Key Points\n"
            for point in conversation['key_points']:
                content += f"- {point}\n"
            content += "\n"
        
        # Add actions taken
        if 'actions' in conversation:
            content += "## Actions Taken\n"
            for action in conversation['actions']:
                content += f"- {action}\n"
            content += "\n"
        
        # Add user input
        if 'user_input' in conversation:
            content += "## User Input\n"
            content += f"{conversation['user_input']}\n\n"
        
        # Add AI responses
        if 'ai_responses' in conversation:
            content += "## AI Responses\n"
            for response in conversation['ai_responses']:
                content += f"> {response}\n\n"
        
        # Add extracted information
        if 'extracted_info' in conversation:
            content += "## Extracted Information\n"
            for category, items in conversation['extracted_info'].items():
                content += f"### {category}\n"
                for item in items:
                    content += f"- {item}\n"
                content += "\n"
        
        return content
    
    def create_person_note(self, name: str, information: Dict[str, Any]) -> str:
        """Create or update a person note"""
        if not self.enabled:
            return ""
        
        # Sanitize filename
        safe_name = re.sub(r'[^\w\s-]', '', name).strip()
        filename = f"{safe_name}.md"
        file_path = self.people_dir / filename
        
        # Check if note exists
        if file_path.exists():
            # Update existing note
            with open(file_path, 'r', encoding='utf-8') as f:
                existing_content = f.read()
            
            # Append new information
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(f"\n\n## Update {datetime.now().strftime('%Y-%m-%d')}\n")
                for key, value in information.items():
                    f.write(f"- {key}: {value}\n")
        else:
            # Create new note
            content = f"# {name}\n\n"
            content += "---\n"
            content += f"created: {datetime.now().isoformat()}\n"
            content += "type: person\n"
            content += "tags:\n"
            content += "  - person\n"
            content += "---\n\n"
            
            content += "## Information\n"
            for key, value in information.items():
                content += f"- {key}: {value}\n"
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        print(f"[Obsidian] 👤 Created/updated person note: {safe_name}")
        return safe_name
    
    def create_project_note(self, project_name: str, details: Dict[str, Any]) -> str:
        """Create or update a project note"""
        if not self.enabled:
            return ""
        
        safe_name = re.sub(r'[^\w\s-]', '', project_name).strip()
        filename = f"{safe_name}.md"
        file_path = self.projects_dir / filename
        
        content = f"# {project_name}\n\n"
        content += "---\n"
        content += f"created: {datetime.now().isoformat()}\n"
        content += "type: project\n"
        content += "tags:\n"
        content += "  - project\n"
        if 'status' in details:
            content += f"  - project/{details['status']}\n"
        content += "---\n\n"
        
        if 'description' in details:
            content += f"## Description\n{details['description']}\n\n"
        
        if 'goals' in details:
            content += "## Goals\n"
            for goal in details['goals']:
                content += f"- [ ] {goal}\n"
            content += "\n"
        
        if 'tasks' in details:
            content += "## Tasks\n"
            for task in details['tasks']:
                content += f"- [ ] {task}\n"
            content += "\n"
        
        if 'notes' in details:
            content += "## Notes\n"
            for note in details['notes']:
                content += f"- {note}\n"
            content += "\n"
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"[Obsidian] 📁 Created project note: {safe_name}")
        return safe_name
    
    def search_notes(self, query: str) -> List[Dict[str, str]]:
        """Search for notes in the vault"""
        if not self.enabled:
            return []
        
        results = []
        
        # Search in all markdown files
        for md_file in self.vault_path.rglob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                if query.lower() in content.lower():
                    # Extract title (first line with #)
                    title = md_file.stem
                    for line in content.split('\n')[:10]:
                        if line.startswith('#'):
                            title = line.lstrip('#').strip()
                            break
                    
                    results.append({
                        'title': title,
                        'path': str(md_file.relative_to(self.vault_path)),
                        'snippet': content[:200]
                    })
            except Exception as e:
                print(f"[Obsidian] ⚠️ Error reading {md_file}: {e}")
        
        return results
    
    def get_all_notes(self) -> List[Dict[str, str]]:
        """Get all notes in the vault"""
        if not self.enabled:
            return []
        
        notes = []
        
        for md_file in self.vault_path.rglob("*.md"):
            try:
                with open(md_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Extract title
                title = md_file.stem
                for line in content.split('\n')[:10]:
                    if line.startswith('#'):
                        title = line.lstrip('#').strip()
                        break
                
                # Extract tags from frontmatter
                tags = []
                in_frontmatter = False
                for line in content.split('\n'):
                    if line.strip() == '---':
                        in_frontmatter = not in_frontmatter
                        continue
                    if in_frontmatter and line.strip().startswith('tags:'):
                        tags = [t.strip() for t in line.split(':', 1)[1].split('-') if t.strip()]
                
                notes.append({
                    'title': title,
                    'path': str(md_file.relative_to(self.vault_path)),
                    'tags': tags,
                    'modified': datetime.fromtimestamp(md_file.stat().st_mtime).isoformat()
                })
            except Exception as e:
                print(f"[Obsidian] ⚠️ Error reading {md_file}: {e}")
        
        return notes
    
    def link_notes_with_ai(self, conversation_summary: str, 
                          api_key: str = None) -> List[str]:
        """Use AI to find and link related notes"""
        if not self.enabled:
            return []
        
        # Get all notes
        all_notes = self.get_all_notes()
        
        if not all_notes:
            return []
        
        # Build note summaries for AI
        note_summaries = []
        for note in all_notes:
            note_summaries.append(f"- {note['title']}: {note['tags']}")
        
        # Use AI to find related notes
        # This would call the Gemini API or similar
        # For now, implement a simple keyword-based approach
        
        related = []
        keywords = self._extract_keywords(conversation_summary)
        
        for note in all_notes:
            for keyword in keywords:
                if keyword.lower() in note['title'].lower():
                    related.append(note['title'])
                    break
        
        return related
    
    def _extract_keywords(self, text: str) -> List[str]:
        """Extract keywords from text"""
        # Simple keyword extraction
        words = re.findall(r'\b\w+\b', text.lower())
        
        # Filter out common words
        stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 
                     'be', 'been', 'being', 'have', 'has', 'had', 
                     'do', 'does', 'did', 'will', 'would', 'should',
                     'could', 'may', 'might', 'must', 'shall', 'can',
                     'to', 'of', 'in', 'for', 'on', 'at', 'by', 'from',
                     'with', 'about', 'as', 'into', 'like', 'through',
                     'after', 'over', 'between', 'out', 'against', 'during',
                     'without', 'before', 'under', 'around', 'among'}
        
        keywords = [word for word in words if word not in stop_words and len(word) > 3]
        
        # Return most common keywords
        from collections import Counter
        return [word for word, count in Counter(keywords).most_common(10)]


class ObsidianMemoryBridge:
    """Bridges JARVIS memory to Obsidian vault"""
    
    def __init__(self):
        self.vault = ObsidianVault()
        self.current_conversation: Dict[str, Any] = {}
        self.conversation_active = False
    
    def start_conversation(self, user_input: str):
        """Start tracking a new conversation"""
        self.current_conversation = {
            'user_input': user_input,
            'ai_responses': [],
            'actions': [],
            'key_points': [],
            'extracted_info': {},
            'start_time': datetime.now()
        }
        self.conversation_active = True
        print("[Obsidian] 🎙️ Started new conversation tracking")
    
    def add_ai_response(self, response: str):
        """Add an AI response to the current conversation"""
        if self.conversation_active:
            self.current_conversation['ai_responses'].append(response)
    
    def add_action(self, action: str):
        """Add an action taken to the current conversation"""
        if self.conversation_active:
            self.current_conversation['actions'].append(action)
    
    def add_key_point(self, point: str):
        """Add a key point to the current conversation"""
        if self.conversation_active:
            self.current_conversation['key_points'].append(point)
    
    def add_extracted_info(self, category: str, info: str):
        """Add extracted information to the current conversation"""
        if self.conversation_active:
            if category not in self.current_conversation['extracted_info']:
                self.current_conversation['extracted_info'][category] = []
            self.current_conversation['extracted_info'][category].append(info)
    
    def end_conversation(self, summary: str = None) -> str:
        """End the conversation and save to Obsidian"""
        if not self.conversation_active:
            return ""
        
        self.current_conversation['end_time'] = datetime.now()
        
        if summary:
            self.current_conversation['summary'] = summary
        else:
            # Generate summary from key points
            if self.current_conversation['key_points']:
                self.current_conversation['summary'] = '. '.join(self.current_conversation['key_points'])
            else:
                self.current_conversation['summary'] = f"Conversation from {self.current_conversation['start_time'].strftime('%Y-%m-%d %H:%M')}"
        
        # Find related notes
        related_notes = self.vault.link_notes_with_ai(
            self.current_conversation['summary']
        )
        
        # Create note
        note_title = self.vault.create_conversation_note(
            self.current_conversation,
            related_notes
        )
        
        # Extract and create person notes if mentioned
        if 'extracted_info' in self.current_conversation:
            if 'people' in self.current_conversation['extracted_info']:
                for person in self.current_conversation['extracted_info']['people']:
                    self.vault.create_person_note(person, {
                        'last_mentioned': datetime.now().isoformat(),
                        'context': self.current_conversation['summary'][:100]
                    })
        
        # Reset
        self.conversation_active = False
        self.current_conversation = {}
        
        return note_title
    
    def extract_persons_from_conversation(self, text: str) -> List[str]:
        """Extract person names from conversation text"""
        # Simple person extraction - would be better with NLP
        # Look for capitalized words that might be names
        words = text.split()
        persons = []
        
        for i, word in enumerate(words):
            # Check if word is capitalized and not at start of sentence
            if word[0].isupper() and i > 0:
                # Check if it's likely a name (not common words)
                if word.lower() not in ['the', 'this', 'that', 'these', 'those']:
                    persons.append(word.strip('.,!?'))
        
        return list(set(persons))  # Remove duplicates


# Global instance
_obsidian_bridge: Optional[ObsidianMemoryBridge] = None


def get_obsidian_bridge() -> ObsidianMemoryBridge:
    """Get the global Obsidian bridge instance"""
    global _obsidian_bridge
    if _obsidian_bridge is None:
        _obsidian_bridge = ObsidianMemoryBridge()
    return _obsidian_bridge
