import pandas as pd
import re
import joblib
import nltk
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.svm import LinearSVC
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk.stem import WordNetLemmatizer

# --- 1. SETUP ---
MODEL_DIR = Path("models")
MODEL_DIR.mkdir(parents=True, exist_ok=True)
MODEL_PATH = MODEL_DIR / "resume_pipeline.joblib"
REPORT_PATH = MODEL_DIR / "resume_pipeline_report.txt"
DATA_PATH = Path("UpdatedResumeDataSet.csv")

# Download NLTK data if not present
try:
    nltk.data.find('corpora/wordnet.zip')
except LookupError:
    print("Downloading NLTK WordNet...")
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)
try:
    stopwords.words("english")
except LookupError:
    print("Downloading NLTK stopwords...")
    nltk.download("stopwords", quiet=True)
    nltk.download("punkt", quiet=True)

# --- 2. TEXT PREPROCESSING ---
lemmatizer = WordNetLemmatizer()
stop_words = set(stopwords.words("english"))

def preprocess_text(text):
    if not isinstance(text, str):
        return ""
    
    text = re.sub(r'http\S+', '', text)            # Remove URLs
    text = re.sub(r'\S*@\S*\s?', '', text)         # Remove email addresses
    text = re.sub(r'[^a-zA-Z\s]', '', text)        # Remove punctuation and numbers
    text = re.sub(r'\s+', ' ', text).strip()       # Remove extra whitespace
    text = text.lower()
    
    tokens = word_tokenize(text)
    lemmatized_tokens = [lemmatizer.lemmatize(word) for word in tokens if word not in stop_words]
    
    return " ".join(lemmatized_tokens)

# --- 3. MAIN TRAINING FUNCTION ---
def train_categorizer_model():
    if not DATA_PATH.exists():
        print(f"Error: Dataset not found at '{DATA_PATH}'.")
        return

    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH)
    df.dropna(inplace=True)

    print("Preprocessing resume text...")
    df["processed_resume"] = df["Resume"].apply(preprocess_text)

    X = df["processed_resume"]
    y = df["Category"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    print(f"Data split: {len(X_train)} training samples, {len(X_test)} testing samples.")

    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2), max_df=0.9, min_df=2)),
        ('clf', LinearSVC(C=1, class_weight='balanced', random_state=42, max_iter=2000))
    ])

    print("Training model...")
    pipeline.fit(X_train, y_train)
    print("Training complete.")

    print("\n--- Evaluation ---")
    y_pred = pipeline.predict(X_test)
    report = classification_report(y_test, y_pred)
    print(report)

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("Resume Categorization Model Report\n")
        f.write("="*50 + "\n\n")
        f.write(report)
    print(f"Report saved at '{REPORT_PATH}'")

    print(f"Saving trained model to '{MODEL_PATH}'...")
    joblib.dump(pipeline, MODEL_PATH)
    print("Model saved successfully.")

if __name__ == "__main__":
    train_categorizer_model()
