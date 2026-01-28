import os
import requests
import re
from dotenv import load_dotenv
from collections import Counter
from typing import List, Dict, Tuple
import time
import math
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("⚠️ scikit-learn not available. TF-IDF keyword extraction will use fallback method.")
    TfidfVectorizer = None

import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize, sent_tokenize

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt', quiet=True)

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords', quiet=True)

# -----------------------------------------------------
# 🔐 Load Hugging Face API Key
# -----------------------------------------------------
dotenv_path = os.path.join(os.path.dirname(__file__), ".env")
load_dotenv(dotenv_path)

HF_API_KEY = os.getenv("HF_API_KEY")
if not HF_API_KEY:
    import warnings
    warnings.warn("HF_API_KEY not found in environment variables. Summarization features will not work. "
                  "Please set it in your .env file or as an environment variable.")
    # Don't raise error immediately - allow app to run without summarization

# -----------------------------------------------------
# ⚙️ API Configuration
# -----------------------------------------------------
# Multiple model options for fallback
SUMMARIZATION_MODELS = [
    "facebook/bart-large-cnn",  # Best for general summarization
    "google/pegasus-xsum",      # Alternative for abstractive summaries
    "facebook/bart-base",       # Faster fallback
]

SUMMARIZATION_MODEL = SUMMARIZATION_MODELS[0]
SUMMARIZATION_URL = f"https://api-inference.huggingface.co/models/{SUMMARIZATION_MODEL}"
HEADERS = {"Authorization": f"Bearer {HF_API_KEY}"}

# Max input length for API (BART limit is ~1024 tokens, we use 1500 chars as safe limit)
MAX_INPUT_LENGTH = 1500
CHUNK_OVERLAP = 200  # Overlap between chunks for context preservation


# -----------------------------------------------------
# 🧠 Enhanced Summarization Functions
# -----------------------------------------------------

def chunk_text(text: str, chunk_size: int = MAX_INPUT_LENGTH, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split long text into overlapping chunks with semantic boundary detection."""
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    # Use sentence tokenization for better boundaries
    try:
        sentences = sent_tokenize(text)
        current_chunk = []
        current_length = 0
        
        for sentence in sentences:
            sentence_length = len(sentence)
            
            # If adding this sentence would exceed chunk size, finalize current chunk
            if current_length + sentence_length > chunk_size and current_chunk:
                chunk_text = ' '.join(current_chunk)
                if chunk_text.strip():
                    chunks.append(chunk_text.strip())
                
                # Start new chunk with overlap (last few sentences from previous chunk)
                overlap_sentences = []
                overlap_length = 0
                for s in reversed(current_chunk):
                    if overlap_length + len(s) <= overlap:
                        overlap_sentences.insert(0, s)
                        overlap_length += len(s) + 1
                    else:
                        break
                
                current_chunk = overlap_sentences + [sentence]
                current_length = overlap_length + sentence_length
            else:
                current_chunk.append(sentence)
                current_length += sentence_length + 1
        
        # Add remaining chunk
        if current_chunk:
            chunk_text = ' '.join(current_chunk)
            if chunk_text.strip():
                chunks.append(chunk_text.strip())
        
        return chunks if chunks else [text]
        
    except Exception:
        # Fallback to simple chunking if sentence tokenization fails
        while start < len(text):
            end = start + chunk_size
            
            # Try to break at sentence boundary
            if end < len(text):
                last_period = text.rfind('.', start, end)
                last_newline = text.rfind('\n', start, end)
                break_point = max(last_period, last_newline)
                
                if break_point > start + chunk_size // 2:
                    end = break_point + 1
            
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
            
            start = end - overlap
        
        return chunks if chunks else [text]


def summarize_chunk(text_chunk: str, max_retries: int = 3, timeout: int = 30, model_index: int = 0) -> str:
    """Summarize a single text chunk with retry logic and model fallback."""
    if len(text_chunk.strip()) < 50:
        return text_chunk  # Return as-is if too short
    
    # Check if API key is available
    if not HF_API_KEY:
        return "Summarization unavailable: Hugging Face API key not configured. Please set HF_API_KEY in your .env file."
    
    # Try models in order until one works
    for model_idx in range(model_index, len(SUMMARIZATION_MODELS)):
        model_name = SUMMARIZATION_MODELS[model_idx]
        url = f"https://api-inference.huggingface.co/models/{model_name}"
        
        payload = {"inputs": text_chunk[:MAX_INPUT_LENGTH]}
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    url, 
                    headers=HEADERS, 
                    json=payload,
                    timeout=timeout
                )
                
                if response.status_code == 200:
                    data = response.json()
                    summary = None
                    
                    # Handle different response formats
                    if isinstance(data, list) and len(data) > 0:
                        if "summary_text" in data[0]:
                            summary = data[0]["summary_text"]
                        elif "generated_text" in data[0]:
                            summary = data[0]["generated_text"]
                    
                    if isinstance(data, dict):
                        if "summary_text" in data:
                            summary = data["summary_text"]
                        elif "generated_text" in data:
                            summary = data["generated_text"]
                    
                    if summary:
                        return summary.strip()
                
                elif response.status_code == 503:
                    # Model is loading, wait and retry
                    wait_time = (attempt + 1) * 5
                    print(f"⏳ Model {model_name} loading, waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    # Try next model if this one fails
                    if model_idx < len(SUMMARIZATION_MODELS) - 1:
                        print(f"⚠️ Model {model_name} failed ({response.status_code}), trying next model...")
                        break
                    else:
                        error_msg = f"Error {response.status_code}: {response.text[:200]}"
                        if attempt == max_retries - 1:
                            return f"Failed to summarize: {error_msg}"
                        time.sleep(2 ** attempt)
            
            except requests.exceptions.Timeout:
                if model_idx < len(SUMMARIZATION_MODELS) - 1:
                    print(f"⚠️ Model {model_name} timed out, trying next model...")
                    break
                elif attempt == max_retries - 1:
                    return "Summarization timed out. Text may be too long."
                time.sleep(2 ** attempt)
            
            except Exception as e:
                if model_idx < len(SUMMARIZATION_MODELS) - 1:
                    print(f"⚠️ Model {model_name} error: {e}, trying next model...")
                    break
                elif attempt == max_retries - 1:
                    return f"Summarization error: {str(e)}"
                time.sleep(2 ** attempt)
    
    return "Could not generate summary after trying all models."


def summarize_text(text: str, max_length: int = None, min_length: int = None, strategy: str = "chunked") -> str:
    """
    Enhanced text summarization with chunking support for long texts.
    
    Args:
        text: Input text to summarize
        max_length: Maximum length of summary (optional)
        min_length: Minimum length of summary (optional)
        strategy: "chunked" for long texts, "direct" for short texts
    """
    if len(text.strip()) < 50:
        return "Text too short to summarize."
    
    # Prepare API parameters
    api_params = {}
    if max_length:
        api_params["parameters"] = {"max_length": max_length}
    if min_length:
        if "parameters" not in api_params:
            api_params["parameters"] = {}
        api_params["parameters"]["min_length"] = min_length
    
    # For short texts, use direct summarization
    if len(text) <= MAX_INPUT_LENGTH and strategy != "chunked":
        return summarize_chunk(text)
    
    # For long texts, use chunking strategy
    chunks = chunk_text(text)
    
    if len(chunks) == 1:
        return summarize_chunk(chunks[0])
    
    # Summarize each chunk
    print(f"📝 Summarizing {len(chunks)} chunks...")
    chunk_summaries = []
    for i, chunk in enumerate(chunks):
        print(f"   Processing chunk {i+1}/{len(chunks)}...")
        summary = summarize_chunk(chunk)
        chunk_summaries.append(summary)
        time.sleep(0.5)  # Rate limiting
    
    # Combine chunk summaries
    combined_text = " ".join(chunk_summaries)
    
    # If combined summary is still long, summarize again
    if len(combined_text) > MAX_INPUT_LENGTH:
        return summarize_chunk(combined_text)
    
    return combined_text


# -----------------------------------------------------
# 🔑 Enhanced Keyword Extraction (TF-IDF + NLP-based)
# -----------------------------------------------------

def extract_keywords_tfidf(text: str, num_keywords: int = 5, ngram_range: Tuple[int, int] = (1, 2)) -> List[Tuple[str, float]]:
    """Extract keywords using enhanced TF-IDF with better filtering and scoring."""
    if len(text.strip()) < 50:
        return []
    
    # Fallback if sklearn is not available
    if not SKLEARN_AVAILABLE:
        return extract_keywords_simple(text, num_keywords)
    
    try:
        # Get NLTK stopwords
        try:
            nltk_stopwords = set(stopwords.words('english'))
        except:
            nltk_stopwords = set()
        
        # Enhanced custom stopwords
        custom_stopwords = {
            "the", "and", "for", "with", "that", "this", "from", "have", "will",
            "your", "about", "there", "their", "them", "they", "been", "were", "are",
            "was", "you", "but", "can", "all", "any", "not", "use", "using", "when",
            "into", "each", "more", "some", "then", "these", "than", "what", "which",
            "also", "such", "because", "very", "many", "much", "like", "other", "one",
            "two", "first", "second", "would", "could", "should", "may", "might",
            "said", "says", "get", "got", "make", "made", "take", "took", "see",
            "know", "think", "way", "well", "even", "back", "here", "just", "only"
        }
        all_stopwords = nltk_stopwords.union(custom_stopwords)
        
        # Initialize TF-IDF vectorizer with better parameters
        vectorizer = TfidfVectorizer(
            ngram_range=ngram_range,
            stop_words=list(all_stopwords),
            max_features=num_keywords * 5,  # Get more candidates for better selection
            min_df=1,
            max_df=0.9,  # Slightly stricter to avoid common words
            lowercase=True,
            token_pattern=r'\b[a-zA-Z]{3,}\b'  # Only words with 3+ letters
        )
        
        # Fit and transform
        tfidf_matrix = vectorizer.fit_transform([text])
        feature_names = vectorizer.get_feature_names_out()
        scores = tfidf_matrix.toarray()[0]
        
        # Get top keywords with scores and filter
        keyword_scores = list(zip(feature_names, scores))
        keyword_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Filter out very short or low-scoring keywords
        filtered_keywords = [
            (kw, score) for kw, score in keyword_scores 
            if len(kw) >= 3 and score > 0.1
        ]
        
        return filtered_keywords[:num_keywords]
    
    except Exception as e:
        print(f"⚠️ TF-IDF extraction failed: {e}, falling back to simple method")
        return extract_keywords_simple(text, num_keywords)


def extract_keywords_simple(text: str, num_keywords: int = 5) -> List[Tuple[str, float]]:
    """Fallback simple keyword extraction method."""
    # Remove unwanted chars and lowercase
    cleaned_text = re.sub(r"[^a-zA-Z0-9\s]", "", text.lower())
    
    # Split into words
    words = cleaned_text.split()
    
    # Common stop words
    stop_words = set([
        "the", "and", "for", "with", "that", "this", "from", "have", "will",
        "your", "about", "there", "their", "them", "they", "been", "were", "are",
        "was", "you", "but", "can", "all", "any", "not", "use", "using", "when",
        "into", "each", "more", "some", "then", "these", "than", "what", "which",
        "also", "such", "because", "very", "many", "much", "like", "other"
    ])
    
    # Remove stop words and short words
    filtered_words = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Create bi-grams and tri-grams
    bigrams = [f"{filtered_words[i]} {filtered_words[i+1]}" 
               for i in range(len(filtered_words)-1)]
    trigrams = [f"{filtered_words[i]} {filtered_words[i+1]} {filtered_words[i+2]}" 
                for i in range(len(filtered_words)-2)]
    
    all_terms = filtered_words + bigrams + trigrams
    
    # Count most common with frequency as score
    term_counts = Counter(all_terms)
    total_count = sum(term_counts.values())
    
    keyword_scores = [(term, count / total_count) 
                      for term, count in term_counts.most_common(num_keywords)]
    
    return keyword_scores


def extract_keywords(text: str, num_keywords: int = 5, method: str = "tfidf", return_scores: bool = False) -> List[str]:
    """
    Enhanced keyword extraction with multiple methods.
    
    Args:
        text: Input text
        num_keywords: Number of keywords to extract
        method: "tfidf" (default) or "simple"
        return_scores: If True, return list of (keyword, score) tuples
    
    Returns:
        List of keywords or list of (keyword, score) tuples
    """
    if len(text.strip()) < 50:
        return [] if not return_scores else []
    
    if method == "tfidf":
        keyword_scores = extract_keywords_tfidf(text, num_keywords)
    else:
        keyword_scores = extract_keywords_simple(text, num_keywords)
    
    if return_scores:
        return keyword_scores
    
    return [keyword for keyword, _ in keyword_scores]


# -----------------------------------------------------
# 🌐 Suggest Related Study Resources
# -----------------------------------------------------
def get_related_resources(keywords):
    """Return YouTube + Google links for each keyword."""
    resources = {}
    for kw in keywords:
        query = kw.replace(" ", "+")
        youtube_link = f"https://www.youtube.com/results?search_query={query}+explained"
        google_link = f"https://www.google.com/search?q={query}+tutorial+site:edu+OR+site:wikipedia.org"
        resources[kw] = (
            f"[📺 YouTube: {kw} Explained]({youtube_link})  \n"
            f"[🌐 Web: {kw} Resources]({google_link})"
        )
    return resources
