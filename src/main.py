import logging
import os
import time
import platform
import joblib
import mlflow
import mlflow.sklearn
from pathlib import Path
from datetime import datetime
from data_loader import load_data, preprocess_data
from evaluate import evaluate
from model import train_model

# Configurar logging (consola + archivo)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler("training.log"),
        logging.StreamHandler()
    ]
)
logger=logging.getLogger("adult-income")

run_name = os.getenv('RUN_NAME', 'run_name not found')

# Paths
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data" / "raw"
MODEL_DIR = PROJECT_ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)

def main():
    mlflow.set_tracking_uri(os.getenv('MLFLOW_TRACKING_URL', 'azureml://spaincentral.api.azureml.ms/mlflow/v1.0/subscriptions/b17a3b65-c9df-48c7-9b32-8cd81f620076/resourceGroups/rg-gcortina-devops/providers/Microsoft.MachineLearningServices/workspaces/mlw-devops'))
    mlflow.set_experiment(os.getenv('EXPERIMENT_NAME', 'experiment_name_not_found'))
    script_start = time.time()
    logger.info(f"System info: {platform.platform()}")

    train_df, test_df = load_data(DATA_DIR / "adult.data", DATA_DIR / "adult.test")
    X_train, X_test, y_train, y_test, scaler, encoders = preprocess_data(train_df, test_df)
    mlflow.autolog()
    with mlflow.start_run(run_name=run_name) as run:
        start_time = time.time()
        model = train_model(X_train, y_train)
        elapsed = time.time() - start_time
        logger.info(f"Model training complete. Time taken: {elapsed:.2f} seconds")
        evaluate(model, X_test, y_test)

        # Save and log model with metadata
        joblib.dump(model, MODEL_DIR / "model.pkl")

        # Save and log scaler and encoders
        joblib.dump(scaler, MODEL_DIR / "scaler.pkl")
        joblib.dump(encoders, MODEL_DIR / "encoders.pkl")

        mlflow.log_artifact(str(MODEL_DIR / "scaler.pkl"), artifact_path="preprocessing")
        mlflow.log_artifact(str(MODEL_DIR / "encoders.pkl"), artifact_path="preprocessing")

        # Write run_id cleanly to workspace root so build.yml can capture it
        run_id_file = PROJECT_ROOT / "run_id.txt"
        with open(run_id_file, "w") as f:
            f.write(run.info.run_id)
        logger.info(f"Saved run ID {run.info.run_id} to {run_id_file}")

    total_time = time.time() - script_start
    logger.info(f"Script completed in {total_time:.2f} seconds.")

if __name__ == "__main__":
    main()