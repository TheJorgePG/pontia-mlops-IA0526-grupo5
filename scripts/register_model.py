import mlflow
from mlflow.tracking import MlflowClient
import os
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Set the tracking URI
tracking_url = os.getenv('MLFLOW_TRACKING_URL')
if not tracking_url:
    raise ValueError("MLFLOW_TRACKING_URL is not set")

mlflow.set_tracking_uri(tracking_url)
logger.info(f"MLflow Tracking URI: {tracking_url}")

client = MlflowClient()

# Get model info from environment
run_id = os.getenv('RUN_ID')
model_name = os.getenv("MODEL_NAME")

if not run_id or run_id == 'run_id not found':
    raise ValueError(f"RUN_ID is invalid: {run_id}")
if not model_name or model_name == 'no_name':
    raise ValueError(f"MODEL_NAME is invalid: {model_name}")

logger.info(f"Registering model: {model_name} from run: {run_id}")

model_uri = f"runs:/{run_id}/model"

try:
    # Register the model
    result = mlflow.register_model(
        model_uri=model_uri,
        name=model_name
    )
    logger.info(f"Model registered: {model_name} v{result.version}")
except Exception as e:
    logger.error(f"Failed to register model: {e}")
    raise

try:
    # Transition to Production stage (Azure ML standard)
    client.transition_model_version_stage(
        name=model_name,
        version=result.version,
        stage="Production"
    )
    logger.info(f"Model {model_name} v{result.version} transitioned to Production stage")
except Exception as e:
    logger.error(f"Failed to transition model: {e}")
    raise

# Verify the model exists in Production
try:
    model_versions = client.search_model_versions(f"name='{model_name}'")
    prod_versions = [mv for mv in model_versions if mv.current_stage == "Production"]
    if prod_versions:
        logger.info(f"✓ Verified: {model_name} found in Production stage (versions: {[mv.version for mv in prod_versions]})")
    else:
        logger.warning(f"⚠ No versions found in Production stage for {model_name}")
except Exception as e:
    logger.error(f"Failed to verify model: {e}")

