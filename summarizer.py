import re
import math
from datetime import datetime

# A standard set of English stopwords to clean out from text before word frequency calculations
STOPWORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours", 
    "yourself", "yourselves", "he", "him", "his", "himself", "she", "her", "hers", "herself", 
    "it", "its", "itself", "they", "them", "their", "theirs", "themselves", "what", "which", 
    "who", "whom", "this", "that", "these", "those", "am", "is", "are", "was", "were", "be", 
    "been", "being", "have", "has", "had", "having", "do", "does", "did", "doing", "a", "an", 
    "the", "and", "but", "if", "or", "because", "as", "until", "while", "of", "at", "by", 
    "for", "with", "about", "against", "between", "into", "through", "during", "before", 
    "after", "above", "below", "to", "from", "up", "down", "in", "out", "on", "off", "over", 
    "under", "again", "further", "then", "once", "here", "there", "when", "where", "why", 
    "how", "all", "any", "both", "each", "few", "more", "most", "other", "some", "such", 
    "no", "nor", "not", "only", "own", "same", "so", "than", "too", "very", "s", "t", "can", 
    "will", "just", "don", "should", "now"
}

# Key patterns and phrase markers that indicate standard task action items in emails
ACTION_PATTERNS = [
    r"\bplease\b",
    r"\bneed\s+to\b",
    r"\baction\s+required\b",
    r"\burgent\s+follow\b",
    r"\breview\s+the\b",
    r"\bconfirm\b",
    r"\bsend\s+me\b",
    r"\breply\s+by\b",
    r"\bdue\s+by\b",
    r"\bdeadline\b",
    r"\blet\s+me\s+know\b",
    r"\bcould\s+you\b",
    r"\bwould\s+you\b",
    r"\bschedule\b",
    r"\bcall\s+at\b",
    r"\bappointment\b",
    r"\btask\b",
    r"\baction\b"
]

ACTION_REGEX = re.compile("|".join(ACTION_PATTERNS), re.IGNORECASE)

def clean_and_normalize_body(body_text: str) -> str:
    """Cleans up email text snippets and removes extra whitespace."""
    if not body_text:
        return ""
    # Strip common signature and footer indicators if possible
    # (Matches simple text cutoffs like '--' or 'Best regards')
    body_text = re.split(r"^\s*--\s*$", body_text, flags=re.MULTILINE)[0]
    
    # Normalize multiple whitespaces
    body_text = re.sub(r"\s+", " ", body_text)
    return body_text.strip()

def split_sentences(text: str) -> list:
    """Splits a body of text into individual sentences using regex patterns."""
    if not text:
        return []
    # Match sentence endings (. or ? or !) followed by spaces and a capital letter/end
    sentence_endings = re.compile(r'(?<!\w\.\w.)(?<![A-Z][a-z]\.)(?<=\.|\?|\!)\s')
    sentences = sentence_endings.split(text)
    return [s.strip() for s in sentences if s.strip()]

def extract_summary(body_text: str, num_sentences: int = 2) -> str:
    """
    Computes sentence significance scores using a TF-IDF style local word frequency
    matrix, and returns the top sentences as an extractive summary.
    """
    normalized_body = clean_and_normalize_body(body_text)
    if not normalized_body:
        return "No body text available to summarize."
        
    sentences = split_sentences(normalized_body)
    if len(sentences) <= num_sentences:
        return " ".join(sentences)
        
    # 1. Build word frequency dictionary
    word_frequencies = {}
    words = re.findall(r"\b[a-zA-Z]{3,15}\b", normalized_body.lower())
    
    for word in words:
        if word not in STOPWORDS:
            word_frequencies[word] = word_frequencies.get(word, 0) + 1
            
    if not word_frequencies:
        return " ".join(sentences[:num_sentences])
        
    # 2. Score sentences based on word frequencies
    sentence_scores = []
    for idx, sentence in enumerate(sentences):
        sentence_words = re.findall(r"\b[a-zA-Z]{3,15}\b", sentence.lower())
        raw_score = sum(word_frequencies.get(w, 0) for w in sentence_words)
        
        # Normalize score by log sentence length to avoid long sentence dominance
        word_count = len(sentence_words)
        if word_count > 0:
            # We add a scaling factor to keep score normalized and penalize overly short/long lines
            normalized_score = raw_score / (1 + math.log(word_count + 1))
            # Also penalize sentences with unsubscribing signatures
            if "unsubscribe" in sentence.lower() or "opt out" in sentence.lower():
                normalized_score *= 0.1
        else:
            normalized_score = 0
            
        sentence_scores.append((idx, sentence, normalized_score))
        
    # 3. Sort sentences by score and pick top N
    top_scores = sorted(sentence_scores, key=lambda x: x[2], reverse=True)[:num_sentences]
    
    # 4. Sort chosen sentences back to original chronological order
    top_scores_chronological = sorted(top_scores, key=lambda x: x[0])
    
    summary = " ".join(item[1] for item in top_scores_chronological)
    return summary

def extract_action_items(body_text: str) -> list:
    """
    Scans each sentence in the email text to isolate concrete tasks
    indicated by standard action-item phrase matchers.
    """
    normalized_body = clean_and_normalize_body(body_text)
    if not normalized_body:
        return []
        
    sentences = split_sentences(normalized_body)
    actions = []
    
    for sentence in sentences:
        # Avoid signature elements or privacy rules
        if "privacy policy" in sentence.lower() or "all rights reserved" in sentence.lower():
            continue
            
        if ACTION_REGEX.search(sentence):
            # Clean up leading dots/dashes
            cleaned = re.sub(r"^[-*\s+•]+", "", sentence).strip()
            # Truncate overly long sentences to keep them actionable
            if len(cleaned) > 120:
                cleaned = cleaned[:117] + "..."
            if cleaned not in actions:
                actions.append(cleaned)
                
    return actions[:5] # Return top 5 action items maximum

def generate_daily_digest(emails: list) -> dict:
    """
    Compiles summaries and action items of important emails received over the 
    last 24 hours into a structured JSON-like dictionary.
    """
    summaries = []
    all_actions = []
    
    for email in emails:
        # We only summarize high-priority messages to keep the digest sharp
        if not email.get("is_important"):
            continue
            
        subject = email.get("subject", "No Subject")
        sender = email.get("sender", "Unknown Sender")
        body = email.get("body_snippet", "")
        
        # Generate summary
        summary = extract_summary(body, num_sentences=2)
        summaries.append({
            "subject": subject,
            "sender": sender,
            "summary": summary
        })
        
        # Extract actions
        actions = extract_action_items(body)
        for act in actions:
            all_actions.append({
                "task": act,
                "context_subject": subject,
                "context_sender": sender,
                "completed": False
            })
            
    return {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "summaries": summaries,
        "action_items": all_actions
    }
