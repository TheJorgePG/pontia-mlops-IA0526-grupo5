# 💼 Adult Income — Proyecto de DevOps · Grupo 05

Proyecto de la asignatura de **Introducción a DevOps**. Sí, por debajo hay un modelo de *machine
learning* que predice si una persona gana más o menos de 50.000 $ al año… pero **eso es lo de menos**.

Lo que de verdad va este repo es de **CI/CD**: montar tres pipelines de GitHub Actions que se encargan
de probar el código en cada Pull Request, entrenar y registrar el modelo cuando algo entra en `main`, y
desplegar una API en Azure con un botón. El modelo es la excusa; **el trabajo está en los workflows**.

<p align="center">
  <img alt="GitHub Actions" src="https://img.shields.io/badge/GitHub%20Actions-2088FF?logo=githubactions&logoColor=white">
  <img alt="Docker" src="https://img.shields.io/badge/Docker-2496ED?logo=docker&logoColor=white">
  <img alt="Azure" src="https://img.shields.io/badge/Azure%20Container%20Apps-0078D4?logo=microsoftazure&logoColor=white">
  <img alt="MLflow" src="https://img.shields.io/badge/MLflow-2.22-0194E2?logo=mlflow&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.10-3776AB?logo=python&logoColor=white">
</p>

---

## 🚦 Estado del proyecto

🟢 **Terminado y entregable.** Las tres pipelines funcionan y la `main` está protegida.

| Pipeline | Cuándo salta | Estado |
|---|---|---|
| `integration` | en cada Pull Request | ✅ Corre los tests y los comenta en el PR |
| `build` | al mergear a `main` | ✅ Entrena, valida y registra el modelo |
| `deploy` | a mano (botón) | ✅ Construye la imagen y despliega la API |

> 🧑‍🎓 Por el camino nos peleamos con unas cuantas cosas. Lo contamos tal cual pasó en
> [Problemas que nos encontramos](#-problemas-que-nos-encontramos).

---

## 🔀 Las tres pipelines (esto es lo importante)

Están en [`.github/workflows/`](.github/workflows/). La idea de conjunto es esta:

```
   Abres un Pull Request  ─────►  integration.yml   corre los unit tests y los comenta en el PR
                                                     (si fallan → bloquea el merge)

   Se mergea a main       ─────►  build.yml         entrena el modelo, lo valida (accuracy ≥ 0.80)
                                                     y lo registra en Azure ML como "Production"

   Le damos al botón      ─────►  deploy.yml         imagen Docker → GHCR → Azure Container Apps
```

Y la pieza que hace que todo esto sirva de algo: **nadie hace push directo a `main`** (ver
[Contribución](#-contribución)).

### 🧪 `integration.yml` — el guardián de los PRs

> **Se dispara:** en cada `pull_request` (y a mano). · **Job:** `integrate` en `ubuntu-latest`.

| # | Paso | Qué hace |
|---|------|----------|
| 1 | Checkout | La máquina viene vacía: se trae el repo |
| 2 | Setup Python 3.10 | …tampoco trae Python |
| 3 | Install deps | `pip install -r requirements.txt` |
| 4 | **Unit tests** | `pytest unit_tests` con coverage, **sin morirse si fallan** (`continue-on-error`) |
| 5 | **Comentar en el PR** | Un bot publica el resultado de los tests **dentro del propio Pull Request** |
| 6 | **Fallar si tocaba** | Si los tests fallaron, `exit 1` → el rule set bloquea el merge |

Lo no evidente son los pasos 4 y 6: los tests **no tumban la ejecución al fallar**, para poder llegar
al paso 5 y comentar el resultado igualmente. Después ya lo hacemos fallar nosotros a propósito. Es la
pipeline más vistosa, porque **se ejecuta sobre el PR que la revisa** y deja el comentario ahí mismo.

### 🏗️ `build.yml` — entrenar y registrar

> **Se dispara:** en `push` a `main` (y a mano). · Entrenar es caro, por eso solo aquí.

| # | Paso | Qué hace |
|---|------|----------|
| 1 | `RUN_NAME` con fecha | Para distinguir cada entrenamiento en MLflow |
| 2-4 | Checkout · Python · deps | Lo de siempre |
| 5 | **Login en Azure** | `azure/login` — sin identidad, MLflow no puede subir nada |
| 6 | Descargar el dataset | Los datos **no están en git**, se bajan de la UCI |
| 7 | **Entrenar** | `python src/main.py` → genera los `.pkl` y el `run_id.txt` |
| 8 | Guardar `RUN_ID` | Lo lee del fichero y lo pasa a los pasos siguientes |
| 9 | **Tests del modelo** | El *quality gate*: ¿*accuracy* ≥ 0.80? |
| 10 | **Registrar en MLflow** | Sube el modelo a Azure ML, stage `Production` |

La clave está en el **orden de 9 y 10**: los tests van **antes** del registro. Si el modelo sale malo,
la pipeline se corta en el 9 y **el 10 nunca se ejecuta** → un modelo malo no entra en el registro y,
por tanto, tampoco se puede desplegar. El orden es la protección.

### 🚀 `deploy.yml` — desplegar la API

> **Se dispara:** solo a mano (`workflow_dispatch`). Desplegar es lo más delicado.

| # | Paso | Qué hace |
|---|------|----------|
| 1 | Checkout | Necesita el `Dockerfile` y `deployment/app` |
| 2 | Login en `ghcr.io` | El almacén de imágenes de GitHub — usa el `GH_PAT` |
| 3 | Nombre a minúsculas | `ghcr.io` no admite mayúsculas y el repo sí las tiene |
| 4 | **Build & push** | La imagen con **dos etiquetas**: `:latest` y `:<nº de run>` (para rollback) |
| 5 | Login en Azure | Otra autenticación, contra otro servicio |
| 6 | **Desplegar** | Le da a la Container App la imagen nueva + las variables de entorno |
| 7 | **Esperar al `/health`** | Hace *polling* hasta que la API responde `200` (hasta 30 intentos) |
| 8 | Imprimir la URL | Del Swagger, para no buscarla en el portal de Azure |

Dos cosas que no son adorno: la imagen **no lleva el modelo dentro** (la API se lo baja de Azure ML al
arrancar), y el paso 7 es imprescindible porque Azure puede decir "recibido" y **luego** tener la API
caída mientras descarga el modelo.

**Infra del grupo 05:** Container App `ca-ml-api-grupo05` · resource group `rg-gcortina-devops` ·
región `spaincentral`.

---

## 🔑 Secretos y variables

Ni una credencial vive en el código: todo entra por **secretos** (ocultos) y **variables** (visibles)
del repo, en `Settings → Secrets and variables → Actions`.

### 🔒 Secretos (el valor va oculto, ni nosotros lo vemos)

| Nombre | Para qué |
|---|---|
| `MLFLOW_TRACKING_URL` | La dirección del MLflow de Azure (dónde subir/bajar el modelo) |
| `AZURE_CREDENTIALS` | El JSON del *service principal*: con qué identidad entramos en Azure |
| `GH_PAT` | La llave para subir la imagen a GHCR y que Azure pueda bajársela |

### 👁️ Variables (el valor es visible)

| Nombre | Valor | Para qué |
|---|---|---|
| `EXPERIMENT_NAME` | `grupo05-adult-income` | Cómo se llama el experimento en MLflow |
| `MODEL_NAME` | `adult-income-classifier` | Cómo se registra el modelo (`build` lo guarda con ese nombre y `deploy` lo pide igual) |

> ⚠️ Los valores de los **secretos** no se escriben **nunca** en un fichero (ni `.env`, ni notas): git
> guarda el historial para siempre, así que si subes una credencial y la borras después, sigue ahí.
> Solo se pegan a mano en la pantalla de Settings. Las **variables** sí pueden ir a la vista, porque no
> son sensibles: son solo configuración.

---

## 🤝 Contribución

En `main` **no se hace push directo**. Está protegida con un **rule set** (`Settings → Rules`) que
exige: Pull Request obligatorio, **1 aprobación** de un compañero, y que el check `integrate` esté en
verde. Además bloquea `force push` y el borrado de la rama.

El ciclo que seguimos para cualquier cambio:

1. **Partir de `main` actualizado** y crear rama:
   ```bash
   git checkout main && git pull
   git checkout -b feat/mi-mejora
   ```
2. **Hacer el cambio**, comprobar los tests en local:
   ```bash
   export PYTHONPATH=src && pytest unit_tests
   ```
3. **Subir la rama y abrir el PR** hacia `main`:
   ```bash
   git push -u origin feat/mi-mejora
   ```
   Al abrirlo salta sola la pipeline `integration` y el bot deja los resultados comentados en el PR.
4. **Pedir el code review** a un compañero. Ojo: **no puedes aprobar tu propio PR**, así que nos lo
   repartimos: cada uno abre uno y revisa el del otro.
5. Aprobado y en verde → **merge**. Al entrar en `main`, salta `build`.

---

## ⚙️ Instalación (para probarlo en local)

En serio, lo suyo es verlo correr en las pipelines. Pero si quieres montarlo en tu máquina:

```bash
git clone https://github.com/TheJorgePG/pontia-mlops-IA0526-grupo5.git
cd pontia-mlops-IA0526-grupo5

python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# El dataset no está en git (va en el .gitignore)
mkdir -p data/raw
curl -o data/raw/adult.data https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.data
curl -o data/raw/adult.test https://archive.ics.uci.edu/ml/machine-learning-databases/adult/adult.test

python src/main.py             # entrena y deja los .pkl en models/
```

Tests: `export PYTHONPATH=src && pytest unit_tests` (código) y `pytest model_tests` (modelo entrenado).

---

## 🌐 Uso

### Disparar las pipelines

- `integration` → se lanza sola al abrir un PR (o `Actions → integration → Run workflow`).
- `build` → se lanza sola al mergear a `main` (o a mano).
- `deploy` → `Actions → deploy model → Run workflow`. El último paso **imprime la URL** del Swagger.

### Usar la API ya desplegada

```bash
curl https://<URL-QUE-IMPRIMIO-EL-DEPLOY>/health
# { "status": "ok", "worker_state": "ready", "model_loaded": true }

curl -X POST https://<URL>/predict \
  -H "Content-Type: application/json" \
  -d '{ "age": 52, "workclass": "Self-emp-inc", "fnlwgt": 287927, "education": "Doctorate",
        "education-num": 16, "marital-status": "Married-civ-spouse", "occupation": "Exec-managerial",
        "relationship": "Husband", "race": "White", "sex": "Male", "capital-gain": 15024,
        "capital-loss": 0, "hours-per-week": 60, "native-country": "United-States" }'
# { "prediction": [1] }   ← 1 = gana más de 50.000 $ · 0 = 50.000 $ o menos
```

| Método | Ruta | Qué hace |
|--------|------|----------|
| `GET`  | `/health`  | Si el servicio está vivo y si el modelo está cargado |
| `POST` | `/predict` | La predicción de ingresos |
| `GET`  | `/metrics` | Cuántas predicciones se han hecho |
| `GET`  | `/docs`    | El Swagger |

> 💡 Para la demo, haz **dos** predicciones (una de renta alta que dé `1` y otra de renta baja que dé
> `0`): con una sola no demuestras que el modelo distingue de verdad.

---

## 🛠️ Tecnologías

| Ámbito | Lo que usamos |
|---|---|
| **CI/CD** | GitHub Actions (workflows en YAML) |
| **Contenedores** | Docker + GitHub Container Registry (`ghcr.io`) |
| **Despliegue** | Azure Container Apps |
| **Tracking / registro de modelos** | MLflow sobre Azure Machine Learning |
| **API** | FastAPI + Uvicorn |
| **Lenguaje / ML / Testing** | Python 3.10 · scikit-learn, pandas, NumPy · pytest |

---

## 📄 Licencia

Licencia **MIT**: puedes usar, copiar, modificar y distribuir el código libremente manteniendo el
aviso de copyright; se ofrece "tal cual", sin garantías. El *dataset* **Adult** procede del
[UCI Machine Learning Repository](https://archive.ics.uci.edu/dataset/2/adult) (CC BY 4.0).

---

## 🧗 Problemas que nos encontramos

La parte más honesta del README. Nada de esto salió a la primera:

- **No nos aclarábamos con las contribuciones por culpa de las invitaciones.** Entre invitar a los
  compañeros al repo y que cada uno aceptara y quedara con el rol correcto, nos hicimos un lío al
  principio con quién podía hacer qué.

- **Los permisos para aprobar no funcionaban → montamos una organización.** No había forma de que los
  permisos dejaran aprobar los Pull Requests como queríamos. Lo resolvimos **creando una organización**
  y moviendo el repo ahí; con la organización sí pudimos gestionar bien quién aprueba qué.

- **Quisimos reducir el "límite salarial" y no lo conseguimos resolver.** En un PR probamos a bajar el
  umbral de `>50K` a `>20K` en el preprocesado. El problema es que en este dataset la etiqueta es
  **literalmente el texto** `>50K` / `<=50K`, así que al comparar contra `>20K` **nada coincide** y
  todas las filas se iban a `0`. Aprendimos que ahí no se comparaba un número, sino una cadena tal cual
  viene del CSV.

- **Forzar un error de verdad costó más de lo que parecía.** Queríamos validar que **con un error no se
  puede aprobar un Pull Request**. Primero probamos a **quitar una librería**… y `integration` no dio
  ningún error (no pasaba por ahí). Entonces **forzamos un error más grave**, pero el pipeline de
  integración tampoco pasaba por ese punto. Al final **forzamos un error directamente en los tests**,
  que es lo que sí rompe la integración. Por consiguiente, en esa misma PR hubo **varios push seguidos**
  hasta dar con la tecla.

> 🎥 Estos cuatro, contados en 20 segundos cada uno, van perfectos para el vídeo: demuestran que
> entendimos **por qué** existe cada pieza y no que copiamos un YAML y ya.

---

<p align="center"><sub>Proyecto de Introducción a DevOps · Grupo 05 💪</sub></p>
