import re
from config import Config
from db import log_event

# Compiled regular expressions for fast matching
AUTO_SENDER_REGEX = re.compile(
    r"(noreply|no-reply|support|newsletter|alert|notification|info|deals|marketing|feedback|jobs-noreply|bounce)",
    re.IGNORECASE
)

PERSONAL_DOMAINS = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com", "me.com", "aol.com", "zoho.com", "protonmail.com", "proton.me"}

# Content Keywords & Weights
HIGH_POSITIVE_KEYWORDS = {
    "interview": 30, "contract": 35, "invoice": 35, "hiring": 25, "proposal": 25, 
    "offer": 20, "meeting": 20, "scheduling": 20, "calendar": 15, "zoom": 15, 
    "payment": 20, "agreed": 15, "agreement": 20, "partnership": 20, "cv": 15
}

MODERATE_POSITIVE_KEYWORDS = {
    "question": 10, "follow up": 15, "follow-up": 15, "urgent": 15, "asap": 15, 
    "attached": 10, "resume": 15, "portfolio": 10, "collaboration": 15
}

HIGH_NEGATIVE_KEYWORDS = {
    "unsubscribe": -40, "view in browser": -30, "opt out": -30, "opt-out": -30, 
    "special offer": -25, "discount": -25, "sale": -25, "coupon": -25, "limited time": -20, 
    "weekly digest": -30, "deals": -20, "promotion": -20, "shop now": -25, "cookie policy": -20,
    "privacy policy": -15, "all rights reserved": -20
}

def analyze_email(headers: dict, body: str) -> dict:
    """
    Classifies an email by evaluating structural headers, sender profiles, and content.
    Returns a dictionary with:
        - score: int (0 to 100)
        - is_important: bool
        - classification_reason: str (concatenated justifications)
    """
    subject = headers.get("subject", "").strip()
    sender = headers.get("from", "").strip().lower()
    to_field = headers.get("to", "").strip().lower()
    
    score = 50  # Start at a neutral score
    reasons = []
    
    # -------------------------------------------------------------
    # Tier 1: Whitelist / Blacklist (Short-circuits)
    # -------------------------------------------------------------
    # Whitelist Check
    for whitelisted in Config.WHITELIST_SENDERS:
        if whitelisted in sender:
            log_event("CLASSIFIER", f"Email from '{sender}' matched Whitelist.")
            return {
                "score": 100,
                "is_important": True,
                "classification_reason": f"Sender domain matches whitelist rule: '{whitelisted}'"
            }
            
    # Blacklist Check
    for blacklisted in Config.BLACKLIST_SENDERS:
        if blacklisted in sender:
            log_event("CLASSIFIER", f"Email from '{sender}' matched Blacklist.")
            return {
                "score": 0,
                "is_important": False,
                "classification_reason": f"Sender domain matches blacklist rule: '{blacklisted}'"
            }
            
    # -------------------------------------------------------------
    # Tier 2: Structural Header & Thread Analysis
    # -------------------------------------------------------------
    # Check if this is a reply or forward to an ongoing thread
    clean_subj = subject.strip()
    if re.match(r'^(re|fwd|fw|aw|vs):\s*', clean_subj, re.IGNORECASE):
        core_subject = re.sub(r'^(re|fwd|fw|aw|vs):\s*', '', clean_subj, flags=re.IGNORECASE).strip()
        import db
        if db.has_matching_thread(core_subject):
            score += 35
            reasons.append("Ongoing conversation thread detected (+35)")

    # List-Unsubscribe Header check (Newsletter / Automated feed signature)
    if "list-unsubscribe" in headers:
        score -= 40
        reasons.append("Contains 'List-Unsubscribe' header (-40)")
        
    # Precedence & Bulk Headers
    precedence = headers.get("precedence", "").lower()
    if precedence in ("bulk", "list", "junk"):
        score -= 20
        reasons.append(f"Precedence header is '{precedence}' (-20)")
        
    # Auto-Submitted or X-Mailer indicators
    auto_submitted = headers.get("auto-submitted", "").lower()
    if auto_submitted and auto_submitted != "no":
        score -= 20
        reasons.append(f"Auto-Submitted header detected: '{auto_submitted}' (-20)")

    # -------------------------------------------------------------
    # Tier 3: Sender & Recipient Profiling
    # -------------------------------------------------------------
    # Bulk Recipient check (penalize if more than 10 recipients in To or Cc)
    cc_field = headers.get("cc", "").strip().lower()
    recipients = [r.strip() for r in (to_field + "," + cc_field).split(",") if r.strip()]
    if len(recipients) > 10:
        score -= 20
        reasons.append(f"Mailing list / bulk recipient list ({len(recipients)} recipients) (-20)")

    # Check if sender address contains automated/bot keywords
    if AUTO_SENDER_REGEX.search(sender):
        score -= 20
        reasons.append("Sender contains automated pattern (e.g. no-reply, newsletter) (-20)")
    else:
        # Check if the domain is a known personal email host (increases direct message likelihood)
        domain_match = re.search(r"@([\w\.-]+)", sender)
        if domain_match:
            domain = domain_match.group(1)
            if domain in PERSONAL_DOMAINS:
                score += 15
                reasons.append("Sender is from a personal email domain (+15)")
                
        # Check for internal domain communication (e.g. colleague within same corporate domain)
        if Config.IMAP_USER and "@" in Config.IMAP_USER:
            user_domain = Config.IMAP_USER.split("@", 1)[1].lower()
            sender_domain = ""
            domain_match = re.search(r"@([\w\.-]+)", sender)
            if domain_match:
                sender_domain = domain_match.group(1).lower()
                
            if user_domain and sender_domain and user_domain == sender_domain:
                if user_domain not in PERSONAL_DOMAINS:
                    score += 25
                    reasons.append(f"Internal domain communication (@{user_domain}) (+25)")
                
    # Direct mention analysis (is it sent explicitly to the user's mailbox?)
    if Config.IMAP_USER and Config.IMAP_USER.lower() in to_field:
        score += 10
        reasons.append("User is directly in the 'To' list (+10)")

    # -------------------------------------------------------------
    # Tier 4: NLP Keyword Scoring (Subject & Body)
    # -------------------------------------------------------------
    text_to_analyze = f"{subject} {subject} {body}".lower()  # Weight subject double
    
    # Positive matches
    pos_score = 0
    matched_pos = []
    for word, weight in HIGH_POSITIVE_KEYWORDS.items():
        if word in text_to_analyze:
            pos_score += weight
            matched_pos.append(word)
            
    for word, weight in MODERATE_POSITIVE_KEYWORDS.items():
        if word in text_to_analyze:
            pos_score += weight
            matched_pos.append(word)
            
    if pos_score > 0:
        score += pos_score
        reasons.append(f"Matched positive keywords: {', '.join(matched_pos)} (+{pos_score})")
        
    # Negative matches
    neg_score = 0
    matched_neg = []
    for word, weight in HIGH_NEGATIVE_KEYWORDS.items():
        if word in text_to_analyze:
            neg_score += weight
            matched_neg.append(word)
            
    if neg_score < 0:
        score += neg_score
        reasons.append(f"Matched negative keywords: {', '.join(matched_neg)} ({neg_score})")

    # Clamp final score to [0, 100]
    final_score = max(0, min(100, score))
    is_important = final_score >= Config.IMPORTANCE_THRESHOLD
    
    reason_str = "; ".join(reasons) if reasons else "No clear indicators; treated as standard priority."
    
    return {
        "score": final_score,
        "is_important": is_important,
        "classification_reason": reason_str
    }
