# Adult Income — Proyecto de DevOps · Grupo 05

Entrega de la asignatura de **Introducción a DevOps**. El proyecto es un modelo de *machine learning*
que predice si una persona gana más o menos de 50.000 $ al año a partir de datos del censo de EE. UU.,
pero el modelo es lo de menos: **lo que se trabaja aquí es la metodología DevOps** que lo rodea.

Alrededor de un modelo deliberadamente sencillo (un RandomForest) montamos toda la maquinaria de un
entorno real de trabajo en equipo: tests automáticos ante cada cambio, credenciales fuera del código,
entrenamiento y registro del modelo automatizados, y el despliegue de una API a la nube. Todo ello a
través de tres pipelines de **integración y despliegue continuos** (CI/CD) sobre GitHub Actions.

<p align="center">
  <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white">
  <img alt="Azure" src="https://img.shields.io/badge/Azure%20Container%20Apps-0078D4?logo=microsoftazure&logoColor=white">
  <img alt="MLflow" src="https://img.shields.io/badge/MLflow-2.22-0194E2?logo=mlflow&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white">
</p>

---

## Descripción

El proyecto pone en práctica los pilares de DevOps aplicados a un caso de MLOps:

| Concepto | Cómo se aplica en el proyecto |
|---|---|
| **Integración continua (CI)** | Los tests se ejecutan solos en cada Pull Request y bloquean el *merge* si algo falla |
| **Despliegue continuo (CD)** | El despliegue de la API es un workflow: construye la imagen y la publica en Azure |
| **Testing automatizado** | Tests unitarios del código, y tests de calidad sobre el modelo ya entrenado |
| **Gestión de secretos y variables** | Las credenciales de Azure y la configuración viven fuera del código |
| **Entrenamiento reproducible** | El modelo se entrena, versiona y registra en Azure ML mediante MLflow |

El *dataset* es el **Adult / Census Income** del repositorio de la UCI, y el modelo es un
`RandomForestClassifier` que clasifica la renta en dos clases (`>50K` / `<=50K`).

---

## Estado del proyecto

**Terminado y entregable.** Las tres pipelines funcionan, el modelo se entrena y se registra en Azure
Machine Learning, y la API queda desplegada en una Azure Container App.

| Pipeline | Se ejecuta | Función |
|---|---|---|
| `integration` | en cada Pull Request | Ejecuta los tests y comenta el resultado en el PR |
| `build` | al integrar en `main` | Entrena, valida y registra el modelo |
| `deploy` | manualmente | Construye la imagen y despliega la API |

---

## Cómo funciona

El proyecto encadena las tres pipelines a lo largo del ciclo de vida del modelo:

```
   Pull Request  ────►  integration.yml   ejecuta los unit tests y comenta el resultado en el PR;
                                           si fallan, el merge queda bloqueado

   Merge a main  ────►  build.yml         entrena el modelo, comprueba que su accuracy ≥ 0.80
                                           y lo registra en Azure ML en el stage "Production"

   Despliegue    ────►  deploy.yml        empaqueta la API en una imagen Docker, la publica en
                                           GHCR y la despliega en Azure Container Apps
```

La rama `main` está protegida, de modo que ningún cambio llega a producción sin haber pasado por los
tests y por la revisión de un compañero.

---

## Los workflows

Son el núcleo del proyecto y están en [`.github/workflows/`](.github/workflows/).

### integration.yml — validación en cada Pull Request

Se dispara con cada `pull_request`. Levanta un entorno con Python 3.10, instala las dependencias y
ejecuta los **tests unitarios** del código con cobertura. Un detalle de diseño: los tests están
configurados para **no cortar la ejecución si fallan**, de forma que la pipeline pueda llegar igualmente
a publicar sus resultados como **comentario dentro del propio Pull Request**. Solo después, en un paso
final, la pipeline se marca como fallida si los tests no pasaron, y es esa marca la que impide el
*merge*. Así, el revisor ve el resultado de los tests sin salir del PR.

### build.yml — entrenamiento y registro del modelo

Se dispara cuando un cambio entra en `main`. Se autentica en Azure, descarga el *dataset* de la UCI
(los datos no se versionan en git) y entrena el modelo con `src/main.py`, que registra el experimento
en MLflow. A continuación ejecuta los **tests del modelo** —el *quality gate*— que exigen una *accuracy*
mínima de 0.80. Solo si el modelo supera ese umbral, el último paso lo **registra en Azure ML** y lo
promociona al stage `Production`. El orden importa: la validación va **antes** del registro, así que un
modelo que no dé la talla nunca llega a registrarse y, por tanto, tampoco puede desplegarse.

### deploy.yml — despliegue de la API

Se lanza manualmente, porque desplegar es la operación más delicada. Construye la **imagen Docker** de
la API y la sube al GitHub Container Registry con dos etiquetas (`latest` y el número de ejecución, que
permite volver a una versión anterior). Después despliega esa imagen en la **Azure Container App**,
pasándole por variables de entorno la dirección de MLflow y las credenciales, porque la imagen no lleva
el modelo dentro: la API se lo descarga de Azure ML al arrancar. Por eso la pipeline no termina cuando
Azure acepta el despliegue, sino que **espera a que el endpoint `/health` responda `200`**, que es la
única señal fiable de que la API está viva y con el modelo cargado.

**Infraestructura del grupo 05:** Container App `ca-ml-api-grupo05`, resource group
`rg-gcortina-devops`, región `spaincentral`.

---

## Secretos y variables

Ninguna credencial vive en el código. La información sensible se gestiona como **secretos** de GitHub
Actions y la configuración no sensible como **variables**:

**Secretos**

| Nombre | Contenido |
|---|---|
| `MLFLOW_TRACKING_URL` | Dirección del servidor de MLflow en Azure |
| `AZURE_CREDENTIALS` | Credenciales del *service principal* con el que se accede a Azure |
| `GH_PAT` | Token para publicar y descargar la imagen en el Container Registry |

**Variables**

| Nombre | Valor | Uso |
|---|---|---|
| `EXPERIMENT_NAME` | `grupo05-adult-income` | Nombre del experimento en MLflow |
| `MODEL_NAME` | `adult-income-classifier` | Nombre con el que se registra el modelo y con el que la API lo solicita |

---

## Estructura del repositorio

```
.github/workflows/     Las tres pipelines: integration, build y deploy
src/                   Código de entrenamiento (carga de datos, modelo, evaluación)
scripts/               Registro del modelo en MLflow
deployment/            Dockerfile y la API (FastAPI) que se despliega
unit_tests/            Tests del código, que corren en cada Pull Request
model_tests/           Tests de calidad del modelo entrenado
```

---

## Tecnologías

| Ámbito | Herramientas |
|---|---|
| **CI/CD** | GitHub Actions |
| **Contenedores** | Docker + GitHub Container Registry |
| **Despliegue** | Azure Container Apps |
| **Registro de modelos** | MLflow sobre Azure Machine Learning |
| **API** | FastAPI + Uvicorn |
| **Modelo y datos** | Python 3.10, scikit-learn, pandas, NumPy |
| **Testing** | pytest |

---

## Instalación

Para reproducir el entrenamiento en local hacen falta **Python 3.10** y **Git**:

```bash
git clone https://github.com/TheJorgePG/pontia-mlops-IA0526-grupo5.git
cd pontia-mlops-IA0526-grupo5

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# El dataset no se versiona (está en el .gitignore)
mkdir -p data/raw
curl -o data/raw/adult.data https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data
curl -o data/raw/adult.test https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test

python src/main.py             # entrena y guarda el modelo en models/
```

---

## Uso

El uso normal del proyecto es a través de la API desplegada. Devuelve la predicción de renta a partir
de los datos de una persona:

```bash
curl -X POST https://<URL-DE-LA-API>/predict \
  -H "Content-Type: application/json" \
  -d '{ "age": 52, "workclass": "Self-emp-inc", "fnlwgt": 287927, "education": "Doctorate",
        "education-num": 16, "marital-status": "Married-civ-spouse", "occupation": "Exec-managerial",
        "relationship": "Husband", "race": "White", "sex": "Male", "capital-gain": 15024,
        "capital-loss": 0, "hours-per-week": 60, "native-country": "United-States" }'
# { "prediction": [1] }   ← 1 = gana más de 50.000 $ · 0 = 50.000 $ o menos
```

| Método | Ruta | Función |
|--------|------|---------|
| `GET`  | `/health`  | Estado del servicio e indica si el modelo está cargado |
| `POST` | `/predict` | Predicción de renta a partir de los datos de entrada |
| `GET`  | `/metrics` | Número total de predicciones realizadas |
| `GET`  | `/docs`    | Documentación interactiva (Swagger) |

---

## Contribución

El repositorio está pensado para trabajo en equipo con la rama `main` protegida. Ningún cambio se
integra directamente en `main`: todo pasa por un **Pull Request** que requiere la **aprobación de al
menos un compañero** (code review) y que la pipeline `integration` esté en verde. La protección de la
rama impide además reescribir o borrar su historial. Este flujo es lo que garantiza que un cambio que
rompa el modelo o los tests se detecte **antes** de llegar a producción, y no después.

---

## Licencia

Licencia **MIT**: el código puede usarse, copiarse, modificarse y distribuirse libremente manteniendo
el aviso de copyright, y se ofrece "tal cual", sin garantías. El *dataset* **Adult** procede del
[UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/2/adult) (CC BY 4.0).

---

## Problemas que nos encontramos

Recogemos aquí las dificultades reales que tuvimos durante el desarrollo, porque forman parte del
aprendizaje del proyecto:

- **Contribuciones e invitaciones.** Al principio nos costó cuadrar las invitaciones de colaborador y
  que cada miembro quedara con el rol correcto, lo que generó confusión sobre quién podía hacer qué.

- **Permisos de aprobación y organización.** Los permisos no dejaban aprobar los Pull Requests como
  necesitábamos. Lo resolvimos creando una **organización** y alojando el repositorio en ella, lo que
  nos permitió gestionar correctamente las aprobaciones.

- **Cambio del umbral de renta.** Quisimos bajar el umbral de `>50K` a `>20K` en el preprocesado, pero
  no producía el efecto esperado: en este *dataset* la etiqueta es el texto literal `>50K` / `<=50K`,
  de modo que al compararla con `>20K` no coincidía ninguna fila y todas se clasificaban como `0`.

- **Forzar un fallo para probar la protección.** Queríamos comprobar que un error impide aprobar un
  Pull Request. Al quitar una librería, la pipeline `integration` no lo detectó, porque su ejecución no
  pasa por ese punto; lo mismo ocurrió con un error más grave. Finalmente **provocamos el fallo en los
  propios tests**, que sí rompe la integración. Por eso en ese Pull Request quedan **varios push
  seguidos**, correspondientes a cada intento.

---

<p align="center"><sub>Proyecto de Introducción a DevOps · Grupo 05</sub></p>
