from fastapi import FastAPI, Request, HTTPException, status
import mlflow.pyfunc
import pandas as pd
import os
from contextlib import asynccontextmanager
import time
import logging
from fastapi.responses import PlainTextResponse
import joblib
from azure.identity import ClientSecretCredential
from pydantic import BaseModel, Field

metrics = {"total_predictions": 0}

model = None
scaler = None
encoders = None
model_loading_status = "initializing" 

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PredictionInput(BaseModel):
    age: int = Field(..., example=39)
    workclass: str = Field(..., example="State-gov")
    fnlwgt: int = Field(..., example=77516)
    education: str = Field(..., example="Bachelors")
    education_num: int = Field(..., alias="education-num", example=13)
    marital_status: str = Field(..., alias="marital-status", example="Never-married")
    occupation: str = Field(..., example="Adm-clerical")
    relationship: str = Field(..., example="Not-in-family")
    race: str = Field(..., example="White")
    sex: str = Field(..., example="Male")
    capital_gain: int = Field(..., alias="capital-gain", example=2174)
    capital_loss: int = Field(..., alias="capital-loss", example=0)
    hours_per_week: int = Field(..., alias="hours-per-week", example=40)
    native_country: str = Field(..., alias="native-country", example="United-States")

    class Config:
        populate_by_name = True

def load_model_artifacts():
    """Load model and preprocessing artifacts from MLflow."""
    global model, scaler, encoders, model_loading_status
    
    try:
        logger.info("Loading ML components from MLflow...")
        
        tenant_id = os.getenv('AZURE_TENANT_ID')
        client_id = os.getenv('AZURE_CLIENT_ID')
        client_secret = os.getenv('AZURE_CLIENT_SECRET')
        
        if tenant_id and client_id and client_secret:
            logger.info("Setting up Azure authentication for MLflow...")
            credential = ClientSecretCredential(
                tenant_id=tenant_id,
                client_id=client_id,
                client_secret=client_secret
            )
        
        mlflow_url = os.getenv('MLFLOW_TRACKING_URL')
        if not mlflow_url:
            raise ValueError("MLFLOW_TRACKING_URL not set")
        
        mlflow.set_tracking_uri(mlflow_url)
        logger.info(f"MLflow Tracking URI: {mlflow_url}")
        
        model_uri = os.getenv("MODEL_URI")
        if not model_uri:
            raise ValueError("MODEL_URI not set")
        
        logger.info(f"Loading model from: {model_uri}")
        model = mlflow.pyfunc.load_model(model_uri)
        logger.info(f"✓ Model loaded successfully")

        run_id = None
        if model_uri.startswith("models:/"):
            client = mlflow.MlflowClient()
            clean_path = model_uri.replace("models:/", "")
            
            if "/" in clean_path:
                model_name, target_stage = clean_path.split("/")
                logger.info(f"Searching for model '{model_name}' in stage '{target_stage}'...")
                
                model_versions = client.search_model_versions(f"name='{model_name}'")
                for mv in model_versions:
                    if mv.current_stage == target_stage:
                        run_id = mv.run_id
                        break
                
                if not run_id:
                    raise ValueError(f"No model version found in stage '{target_stage}'")
        
        elif model_uri.startswith("runs:/"):
            run_id = model_uri.split("/")[1]
        else:
            raise ValueError("Unsupported MODEL_URI format")

        logger.info(f"Downloading artifacts from run: {run_id}")
        scaler_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="preprocessing/scaler.pkl")
        encoders_path = mlflow.artifacts.download_artifacts(run_id=run_id, artifact_path="preprocessing/encoders.pkl")

        scaler = joblib.load(scaler_path)
        encoders = joblib.load(encoders_path)
        
        model_loading_status = "ready"
        logger.info("✓ All model artifacts loaded successfully!")
        
    except Exception as e:
        model_loading_status = f"failed: {str(e)}"
        logger.error(f"Model loading from MLflow failed: {e}", exc_info=True)
        logger.info("Attempting to load from local files as fallback...")
        
        try:
            model_path = "/app/models/model.pkl"
            scaler_path = "/app/models/scaler.pkl"
            encoders_path = "/app/models/encoders.pkl"
            
            if os.path.exists(model_path):
                model = joblib.load(model_path)
                scaler = joblib.load(scaler_path)
                encoders = joblib.load(encoders_path)
                model_loading_status = "ready"
                logger.info("Successfully loaded model from local files!")
        except Exception as fallback_error:
            logger.error(f"Fallback loading also failed: {fallback_error}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    load_model_artifacts()
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/health")
def health():
    return {
        "status": "ok", 
        "worker_state": model_loading_status,
        "model_loaded": (model_loading_status == "ready")
    }

@app.post("/predict")
async def predict(payload: PredictionInput):  # Uses the validated Pydantic model
    global model, scaler, encoders
    
    if model_loading_status != "ready":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model is initializing or unavailable."
        )
        
    start = time.time()
    
    # Dump using aliases to guarantee hyphen names go directly to pandas columns
    body = payload.model_dump(by_alias=True)
    
    feature_columns = [
        "age", "workclass", "fnlwgt", "education", "education-num", "marital-status",
        "occupation", "relationship", "race", "sex", "capital-gain", "capital-loss",
        "hours-per-week", "native-country"
    ]
    
    # 1. Enforce shape and column order immediately
    df = pd.DataFrame([body], columns=feature_columns)

    # 2. Encode categorical fields safely 
    for col, le in encoders.items():
        if col in df.columns:
            df[col] = le.transform(df[col])

    # 3. Transform through the scaler
    df_scaled = scaler.transform(df)

    # 4. Generate inference
    prediction = model.predict(df_scaled)
    metrics["total_predictions"] += 1
    
    return {"prediction": prediction.tolist()}

@app.get("/metrics", response_class=PlainTextResponse)
def metrics_endpoint():
    return f'total_predictions {metrics["total_predictions"]}\n'