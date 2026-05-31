"""
Generate a simple scikit-learn Iris classifier for testing the AI Deploy platform.
Run this script to create a .pkl model file, then upload it via the API.

Usage:
    python scripts/create_test_model.py
"""
import pickle
from pathlib import Path

# Use sklearn's built-in Iris dataset
from sklearn.datasets import load_iris
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

def main():
    print("Loading Iris dataset...")
    iris = load_iris()
    X_train, X_test, y_train, y_test = train_test_split(
        iris.data, iris.target, test_size=0.2, random_state=42
    )

    print("Training RandomForest classifier...")
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)

    # Evaluate
    y_pred = model.predict(X_test)
    accuracy = accuracy_score(y_test, y_pred)
    print(f"Test accuracy: {accuracy:.2%}")

    # Feature names for reference
    print(f"Features: {iris.feature_names}")
    print(f"Classes: {list(iris.target_names)}")

    # Save the model
    output_path = Path(__file__).parent / "test_iris_model.pkl"
    with open(output_path, "wb") as f:
        pickle.dump(model, f)

    print(f"\nModel saved to: {output_path}")
    print(f"File size: {output_path.stat().st_size / 1024:.1f} KB")
    print("\n--- How to test ---")
    print("1. Upload this .pkl file via POST /models/upload (framework='sklearn')")
    print("2. Copy the model_id from the response")
    print("3. Run POST /inference/{model_id}/predict with body:")
    print('   {"inputs": [[5.1, 3.5, 1.4, 0.2]]}')
    print("   (4 features: sepal_length, sepal_width, petal_length, petal_width)")
    print("   Expected: class 0 = setosa, 1 = versicolor, 2 = virginica")


if __name__ == "__main__":
    main()
