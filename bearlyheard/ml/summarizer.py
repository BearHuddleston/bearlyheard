"""Summarization implementation for BearlyHeard"""

import re
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass
from pathlib import Path

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False

from ..utils.logger import LoggerMixin


@dataclass
class SummaryResult:
    """Complete summary result"""
    summary: str
    action_items: List[str]
    key_points: List[str]
    participants: List[str]
    decisions: List[str]
    summary_type: str
    model_name: str


class Summarizer(LoggerMixin):
    """Text summarization using llama.cpp"""
    
    def __init__(self, model_path: Optional[str] = None, n_ctx: int = 4096):
        """
        Initialize summarizer
        
        Args:
            model_path: Path to GGUF model file
            n_ctx: Context window size
        """
        self.model_path = model_path or self._find_default_model()
        self.n_ctx = n_ctx
        self.model = None
        self.is_loaded = False
        self.progress_callback = None
        
        if not HAS_LLAMA:
            self.logger.warning("llama-cpp-python not available, summarization limited")
        else:
            self.logger.info("Summarizer initialized with llama.cpp")
            if self.model_path:
                self.logger.info(f"Model path: {self.model_path}")
            else:
                self.logger.warning("No model found. Download a GGUF model to enable AI summarization.")
    
    def _find_default_model(self) -> Optional[str]:
        """Find a default model in the models directory"""
        
        # Get models directory relative to this file
        models_dir = Path(__file__).parent.parent.parent / "models"
        
        if not models_dir.exists():
            return None
        
        # Look for models in order of preference (most compatible first)
        model_patterns = [
            "**/tinyllama*.gguf",      # TinyLlama - most compatible
            "**/qwen2.5*3b*.gguf",     # Qwen2.5-3B
            "**/qwen3*4b*.gguf",       # Qwen3-4B 
            "**/qwen*.gguf",           # Any Qwen model
            "**/*llama*.gguf",         # Any Llama model
        ]
        
        for pattern in model_patterns:
            matches = list(models_dir.glob(pattern))
            if matches:
                model_path = str(matches[0])
                self.logger.info(f"Found model: {model_path}")
                return model_path
        
        return None
    
    def load_model(self, model_path: Optional[str] = None) -> bool:
        """
        Load the LLM model
        
        Args:
            model_path: Path to GGUF model file
            
        Returns:
            True if model loaded successfully
        """
        if not HAS_LLAMA:
            self.logger.error("Cannot load model: llama-cpp-python not available")
            return False
        
        if self.is_loaded and model_path == self.model_path:
            return True
        
        if model_path:
            self.model_path = model_path
        
        if not self.model_path:
            self.logger.error("No model path specified")
            return False
        
        # Validate model file exists and is readable
        model_file = Path(self.model_path)
        if not model_file.exists():
            self.logger.error(f"Model file does not exist: {self.model_path}")
            return False
        
        if model_file.stat().st_size < 1024:  # Less than 1KB is definitely wrong
            self.logger.error(f"Model file too small: {model_file.stat().st_size} bytes")
            return False
        
        try:
            self.logger.info(f"Loading LLM model: {self.model_path}")
            
            # Use conservative settings to avoid memory issues
            self.model = Llama(
                model_path=str(self.model_path),
                n_ctx=512,  # Very small context like test script
                n_threads=1,  # Single thread like test script
                n_batch=128,  # Small batch like test script
                verbose=True,  # Enable verbose like test script
                use_mmap=True,  # Use memory mapping
                use_mlock=False,  # Don't lock memory
                n_gpu_layers=0,  # Force CPU-only to avoid GPU issues
                seed=42  # Fixed seed for reproducibility
            )
            
            # Test the model with a simple prompt
            test_response = self.model("Hello", max_tokens=5, temperature=0.1)
            if not test_response or 'choices' not in test_response:
                raise Exception("Model test failed - no valid response")
            
            self.is_loaded = True
            self.logger.info(f"LLM model loaded successfully")
            return True
            
        except Exception as e:
            self.logger.error(f"Failed to load LLM model: {e}")
            # Clean up any partial model
            if hasattr(self, 'model') and self.model:
                try:
                    del self.model
                except:
                    pass
                self.model = None
            return False
    
    def set_progress_callback(self, callback: Callable[[float], None]):
        """Set callback for progress updates"""
        self.progress_callback = callback
    
    def summarize(
        self,
        text: str,
        summary_type: str = "executive",
        max_tokens: int = 1000
    ) -> Optional[SummaryResult]:
        """
        Summarize text using LLM
        
        Args:
            text: Text to summarize
            summary_type: Type of summary (executive, detailed, action_items)
            max_tokens: Maximum tokens for summary
            
        Returns:
            Summary result or None if failed
        """
        if not text.strip():
            self.logger.error("Cannot summarize empty text")
            return None
        
        # Try to load model if we have a path but model isn't loaded
        if not HAS_LLAMA:
            self.logger.warning("llama-cpp-python not available, generating rule-based summary")
            return self._create_rule_based_summary(text, summary_type)
        
        if not self.is_loaded and self.model_path:
            self.logger.info("Model not loaded, attempting to load...")
            if not self.load_model():
                self.logger.warning("Failed to load model, generating rule-based summary")
                return self._create_rule_based_summary(text, summary_type)
        
        if not self.is_loaded:
            self.logger.warning("No model available, generating rule-based summary")
            return self._create_rule_based_summary(text, summary_type)
        
        try:
            self.logger.info(f"Starting {summary_type} summarization")
            
            if self.progress_callback:
                self.progress_callback(0.0)
            
            # Generate prompt based on summary type
            prompt = self._create_prompt(text, summary_type)
            
            if self.progress_callback:
                self.progress_callback(0.2)
            
            # Generate summary
            response = self.model(
                prompt,
                max_tokens=max_tokens,
                temperature=0.3,
                top_p=0.9,
                top_k=40,
                repeat_penalty=1.1,
                stop=["</summary>", "\n\n---", "Human:", "Assistant:"]
            )
            
            if self.progress_callback:
                self.progress_callback(0.8)
            
            # Parse response
            summary_text = response["choices"][0]["text"].strip()
            result = self._parse_summary_response(summary_text, summary_type)
            
            if self.progress_callback:
                self.progress_callback(1.0)
            
            self.logger.info(f"Summarization completed: {len(result.summary)} chars")
            return result
            
        except Exception as e:
            self.logger.error(f"Failed to generate summary: {e}")
            return self._create_rule_based_summary(text, summary_type)
    
    def _create_prompt(self, text: str, summary_type: str) -> str:
        """Create appropriate prompt based on summary type"""
        
        if summary_type == "executive":
            prompt = f"""You are an expert meeting assistant. Analyze meeting transcripts and provide comprehensive, structured summaries.

Please analyze this meeting transcript and provide an executive summary:

TRANSCRIPT:
{text}

Provide your response in this exact format:

## EXECUTIVE SUMMARY
[Brief 2-3 sentence overview of the meeting's main purpose and outcomes]

## KEY DECISIONS
- [List each decision made during the meeting]

## ACTION ITEMS  
- [List action items with responsible person if mentioned]

## KEY POINTS
- [List 3-5 most important discussion points]

## PARTICIPANTS
[List participants mentioned in the transcript]"""

        elif summary_type == "detailed":
            prompt = f"""You are an expert meeting assistant. Analyze meeting transcripts and provide comprehensive, structured summaries.

Please analyze this meeting transcript and provide a detailed summary:

TRANSCRIPT:
{text}

Provide your response in this exact format:

## DETAILED SUMMARY
[Comprehensive overview of the meeting covering all major topics discussed]

## DISCUSSION TOPICS
- [Topic 1: Brief description]
- [Topic 2: Brief description]

## DECISIONS MADE
- [Decision 1 with context]
- [Decision 2 with context]

## ACTION ITEMS
- [Action item with owner and deadline if mentioned]

## NEXT STEPS
- [Follow-up actions or next meeting plans]

## PARTICIPANTS
[List all participants and their roles if mentioned]"""

        elif summary_type == "action_items":
            prompt = f"""You are an expert meeting assistant. Analyze meeting transcripts and provide comprehensive, structured summaries.

Please analyze this meeting transcript and extract all action items:

TRANSCRIPT:
{text}

Provide your response in this exact format:

## ACTION ITEMS
- [Action item 1 - Owner: Name - Due: Date if mentioned]
- [Action item 2 - Owner: Name - Due: Date if mentioned]

## DECISIONS REQUIRING FOLLOW-UP
- [Decision 1 and required actions]

## PENDING ITEMS
- [Items that need resolution in future meetings]

## PARTICIPANTS
[List participants mentioned]"""

        else:
            # Default to executive summary
            return self._create_prompt(text, "executive")
        
        return prompt
    
    def _parse_summary_response(self, response: str, summary_type: str) -> SummaryResult:
        """Parse LLM response into structured summary"""
        
        # Extract different sections using regex
        summary = self._extract_section(response, ["EXECUTIVE SUMMARY:", "DETAILED SUMMARY:", "SUMMARY:"])
        action_items = self._extract_list_items(response, ["ACTION ITEMS:", "ACTIONS:"])
        key_points = self._extract_list_items(response, ["KEY DECISIONS:", "MAIN TOPICS:", "KEY POINTS:"])
        participants = self._extract_list_items(response, ["PARTICIPANTS:", "ATTENDEES:"])
        decisions = self._extract_list_items(response, ["DECISIONS MADE:", "DECISIONS:", "KEY DECISIONS:"])
        
        # If extraction fails, fall back to basic parsing
        if not summary:
            summary = response[:500] + "..." if len(response) > 500 else response
        
        return SummaryResult(
            summary=summary,
            action_items=action_items or ["No action items identified"],
            key_points=key_points or ["No key points identified"],
            participants=participants or ["Participants not identified"],
            decisions=decisions or ["No decisions identified"],
            summary_type=summary_type,
            model_name="llama-cpp"
        )
    
    def _extract_section(self, text: str, headers: List[str]) -> str:
        """Extract content under specific headers"""
        for header in headers:
            pattern = rf"{re.escape(header)}\s*\n(.*?)(?=\n[A-Z\s]+:|$)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()
        return ""
    
    def _extract_list_items(self, text: str, headers: List[str]) -> List[str]:
        """Extract list items under specific headers"""
        for header in headers:
            pattern = rf"{re.escape(header)}\s*\n((?:-.*\n?)*)"
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                items = []
                for line in match.group(1).split('\n'):
                    line = line.strip()
                    if line.startswith('-'):
                        items.append(line[1:].strip())
                return items
        return []
    
    def _create_rule_based_summary(self, text: str, summary_type: str) -> SummaryResult:
        """Create summary using rule-based approach when LLM is not available"""
        
        # Basic text analysis
        sentences = [s.strip() for s in text.split('.') if s.strip()]
        words = text.lower().split()
        
        # Extract potential action items (sentences with action words)
        action_words = ['will', 'should', 'need to', 'must', 'action', 'todo', 'follow up', 'assign']
        action_items = []
        
        for sentence in sentences:
            if any(word in sentence.lower() for word in action_words):
                action_items.append(sentence[:100] + "..." if len(sentence) > 100 else sentence)
        
        # Extract potential participants (capitalized names)
        participants = []
        for word in words:
            if word.istitle() and len(word) > 2:
                participants.append(word)
        
        participants = list(set(participants))[:10]  # Limit to 10 unique names
        
        # Create basic summary (first few sentences)
        summary = '. '.join(sentences[:3]) + '.'
        
        # Extract key points (sentences with important keywords)
        key_words = ['important', 'key', 'main', 'primary', 'critical', 'decision', 'agree']
        key_points = []
        
        for sentence in sentences:
            if any(word in sentence.lower() for word in key_words):
                key_points.append(sentence[:80] + "..." if len(sentence) > 80 else sentence)
        
        return SummaryResult(
            summary=summary or "Summary not available (LLM not loaded)",
            action_items=action_items[:5] if action_items else ["No action items identified"],
            key_points=key_points[:5] if key_points else ["No key points identified"], 
            participants=participants[:5] if participants else ["Participants not identified"],
            decisions=["Decisions not identified (LLM required for detailed analysis)"],
            summary_type=summary_type,
            model_name="rule-based"
        )
    
    def get_available_models(self) -> List[str]:
        """Get list of common GGUF model recommendations"""
        return [
            "llama-2-7b-chat.Q4_K_M.gguf",
            "mistral-7b-instruct-v0.1.Q4_K_M.gguf",
            "phi-2.Q4_K_M.gguf",
            "tinyllama-1.1b-chat-v1.0.Q4_K_M.gguf"
        ]
    
    def estimate_processing_time(self, text_length: int) -> float:
        """
        Estimate processing time based on text length
        
        Args:
            text_length: Length of text in characters
            
        Returns:
            Estimated processing time in seconds
        """
        # Rough estimate: ~1000 chars per second
        return max(5.0, text_length / 1000.0)
    
    def clear_model(self):
        """Clear the loaded model to free memory"""
        if self.model:
            del self.model
            self.model = None
            self.is_loaded = False
            self.logger.info("LLM model cleared from memory")