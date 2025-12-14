
import json
import traceback
from llama_index.core import Settings

class AuditService:
    def __init__(self):
        # We assume Settings.llm is already configured (Gemini 1.5 Pro ideally)
        pass

    def run_architecture_audit(self, diffs, architecture_summary, tech_stack):
        """
        Audits the provided diffs against the project architecture and tech stack.
        """
        print("🕵️ AuditService: Analyzing changes...")
        
        diff_str = json.dumps(diffs, indent=2)
        
        prompt = (
            "You are the Gatekeeper Architect for this project.\n"
            f"Project Rules / Architecture: {architecture_summary}\n"
            f"Tech Stack: {tech_stack}\n\n"
            "Incoming Changes (Git Diffs):\n"
            f"{diff_str}\n\n"
            "Mission:\n"
            "1. Analyze IF these specific changes violate the project structure (e.g., direct DB calls in UI, wrong file placement, spaghetti code).\n"
            "2. Check for security risks or bad practices in the new code (hardcoded secrets, SQL injection, etc).\n"
            "3. Ignore huge refactors or deleted files unless critical; focus on the logic changes provided.\n\n"
            "Output JSON ONLY:\n"
            "{\n"
            "  \"score\": 0-100 (Integer representation of code quality/compliance),\n"
            "  \"status\": \"APPROVED\" | \"WARNING\" | \"CRITICAL\",\n"
            "  \"summary\": \"Brief executive summary of the changes.\",\n"
            "  \"issues\": [\n"
            "    { \"file\": \"src/auth.ts\", \"severity\": \"high\", \"message\": \"Hardcoded secret detected.\" }\n"
            "  ]\n"
            "}\n"
            "Respond ONLY with valid JSON."
        )
        
        try:
            response = Settings.llm.complete(prompt)
            text = response.text.strip()
            
            # Clean md blocks
            if text.startswith("```json"):
                text = text[7:-3]
            elif text.startswith("```"):
                text = text[3:-3]
                
            return json.loads(text)
            
        except Exception as e:
            print(f"❌ AuditService Failed: {e}")
            traceback.print_exc()
            return {
                "score": 0,
                "status": "ERROR",
                "summary": "AI Audit failed to execute.",
                "issues": [{"file": "N/A", "severity": "critical", "message": str(e)}]
            }
