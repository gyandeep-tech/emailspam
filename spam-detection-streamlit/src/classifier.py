import os
import io
import joblib
import pandas as pd
from typing import Union, Optional
from sklearn.feature_extraction.text import CountVectorizer
from sklearn.model_selection import train_test_split
from sklearn.naive_bayes import MultinomialNB
from sklearn.metrics import accuracy_score

_vectorizer: Optional[CountVectorizer] = None
_model: Optional[MultinomialNB] = None

def _is_safe_csv_path(path: str) -> bool:
    if not isinstance(path, str):
        return False
    norm = os.path.normpath(path)
    if os.path.isabs(norm):
        return False
    if ".." in norm.split(os.sep):
        return False
    return norm.lower().endswith(".csv")

def _to_binary_labels(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(int)
    s = series.fillna("").astype(str).str.lower().str.strip()
    return s.map(lambda v: 1 if v in ("1", "true", "t", "yes", "y", "spam") else 0).astype(int)

class SpamDetectionClassifier:
    def __init__(self, dataset: Union[str, pd.DataFrame, io.IOBase]):
        if isinstance(dataset, pd.DataFrame):
            self.dataset = dataset.copy()
        elif hasattr(dataset, "read"):
            self.dataset = pd.read_csv(dataset)
        elif isinstance(dataset, str):
            if not _is_safe_csv_path(dataset):
                raise ValueError("Unsafe dataset path. Provide a relative .csv within project.")
            self.dataset = pd.read_csv(dataset)
        else:
            raise ValueError("dataset must be a path, file-like object, or DataFrame")

        self.vectorizer = CountVectorizer()
        self.model = MultinomialNB()
        self.accuracy = None
        self._train_model()

    def _train_model(self):
        if "text" not in self.dataset.columns or "spam" not in self.dataset.columns:
            raise KeyError("Dataset must contain 'text' and 'spam' columns")
        texts = self.dataset["text"].fillna("").astype(str)
        y = _to_binary_labels(self.dataset["spam"])
        stratify = y if y.nunique() > 1 else None
        X = self.vectorizer.fit_transform(texts)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42, stratify=stratify
        )
        self.model.fit(X_train, y_train)
        y_pred = self.model.predict(X_test)
        self.accuracy = accuracy_score(y_test, y_pred)

    def predictMessage(self, message: str) -> str:
        vec = self.vectorizer.transform([message])
        pred = self.model.predict(vec)
        return "Spam" if int(pred[0]) == 1 else "Ham"

    def get_accuracy(self):
        return self.accuracy

    def save(self, path: str):
        """Persist classifier (vectorizer + model) to file using joblib."""
        payload = {"vectorizer": self.vectorizer, "model": self.model}
        joblib.dump(payload, path)

    @classmethod
    def load(cls, path: str):
        """Load a saved classifier (joblib) and return an object-like wrapper."""
        data = joblib.load(path)
        obj = object.__new__(cls)
        obj.vectorizer = data["vectorizer"]
        obj.model = data["model"]
        obj.accuracy = None
        return obj

def load_default_model(path: str = "emails.csv") -> bool:
    """Train module-level default model from a CSV if present. Returns True on success."""
    global _vectorizer, _model
    if not _is_safe_csv_path(path) or not os.path.exists(path):
        _vectorizer = None
        _model = None
        return False
    df = pd.read_csv(path)
    if "text" not in df.columns or "spam" not in df.columns:
        raise KeyError("Default CSV must have 'text' and 'spam' columns")
    _vectorizer = CountVectorizer()
    X = _vectorizer.fit_transform(df["text"].fillna("").astype(str))
    y = _to_binary_labels(df["spam"])
    _model = MultinomialNB()
    _model.fit(X, y)
    return True

def predictMessage(message: str) -> str:
    """Module-level predict; raises if default model not loaded."""
    if _vectorizer is None or _model is None:
        raise RuntimeError("Default model not loaded. Call load_default_model() or use SpamDetectionClassifier.")
    vec = _vectorizer.transform([message])
    pred = _model.predict(vec)
    return "Spam" if int(pred[0]) == 1 else "Ham"