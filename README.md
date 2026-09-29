# AI-Powered Personalized Health Monitoring and Wellness Recommendation System

A production-grade, full-stack wellness platform combining offline-trained machine learning models, deterministic physiological safety layers, real-time telemetry tracking, transparent behavioral scoring, and an intelligent non-clinical health companion.

> **CRITICAL MEDICAL DISCLAIMER:**
> Vitalis AI is a personal health monitoring and lifestyle habit optimization platform. **It does NOT provide medical diagnoses, clinical treatment plans, or emergency triage advice.** The system encourages positive wellness habits (movement, hydration, sleep hygiene, nutritional balance). For acute symptoms, medical emergencies, diagnosis questions, or medication changes, always consult a qualified healthcare professional immediately.

---

## Table of Contents
1. [Project Overview](#1-project-overview)
2. [Hybrid Intelligent Architecture](#2-hybrid-intelligent-architecture)
3. [Machine Learning Models](#3-machine-learning-models)
4. [Technology Stack](#4-technology-stack)
5. [Database Schema](#5-database-schema)
6. [11-Step ML Self-Validation & Bug Diagnostics](#6-11-step-ml-self-validation--bug-diagnostics)
7. [Installation & Setup](#7-installation--setup)
8. [CLI Commands](#8-cli-commands)
9. [Automated Testing & Coverage](#9-automated-testing--coverage)
10. [Model Rollback & Retraining](#10-model-rollback--retraining)
11. [Demo Accounts & Viva Presentation](#11-demo-accounts--viva-presentation)
12. [Privacy & Security](#12-privacy--security)

---

## 1. Project Overview

Vitalis AI bridges the gap between raw wearable telemetry and actionable, evidence-based habit formation:
- **Personalized Biometrics Profile:** Tracks age, gender, height, weight, activity baseline, dietary preferences, wellness goals, and physical limitations.
- **Deterministic Biometrics:** Mathematically calculates BMI and Mifflin-St Jeor Basal Metabolic Rate (BMR) without black-box approximations.
- **Model A (Goal & Recommendation Classifier):** Predicts high-impact wellness categories (`activity_boost`, `sleep_hygiene`, `hydration_focus`, `metabolic_balance`, `strength_endurance`, `active_recovery`) based on 18 physiological and rolling behavioral features.
- **Model B (Transparent Wellness Score):** Computes an empirical daily score (0–100) using configurable behavioral weights (Activity: 25%, Hydration: 20%, Sleep: 20%, Tasks: 20%, Consistency: 15%).
- **Model C (Longitudinal Trend Detector):** Estimates 7-day and 14-day behavioral slopes using linear regression to report factual progress without unfounded clinical claims.
- **Model D (Data Quality Anomaly Screener):** Leverages an unsupervised Isolation Forest to catch data entry typos or extreme deviations without diagnosing diseases.
- **Model E (Personalization Engine):** Uses NearestNeighbors with cosine similarity to identify cohort profiles and calibrate personalized meal and exercise routines.
- **Traceable Explainability:** Every recommendation displays the explicit feature factors and mathematical rationale behind the guidance.
- **Four-Tier Resilience Fallback:** Production ML &rarr; Rollback ML &rarr; Validated Deterministic Heuristics &rarr; Universal Safe Baseline.

---

## 2. Hybrid Intelligent Architecture

```
                  USER INPUT & WEARABLE TELEMETRY
                               |
                               v
                     PYDANTIC DATA VALIDATION
                               |
                               v
                  CENTRALIZED FEATURE ENGINEERING
                               |
           +-------------------+-------------------+
           |                                       |
           v                                       v
    ML PREDICTIONS (Model A)             RULE & SAFETY LAYER
    - HistGradientBoosting               - Allergen Exclusions
    - XGBoost / Random Forest            - Physical Limitation Filters
    - Anomaly Screening (Model D)        - Hydration / Caloric Baselines
           |                                       |
           +-------------------+-------------------+
                               |
                               v
                     RECOMMENDATION SERVICE
                     - Curated Nutrition Engine
                     - Exercise Library Selector
                     - Synchronized Daily Tasks
                               |
                               v
                     TRANSPARENT DASHBOARD
                     - Traceable Rationale ("Why?")
                     - Behavioral Wellness Score
                     - Chart.js Visual Telemetry
```

---

## 3. Machine Learning Models

### Candidate Evaluation & Empirical Selection
Rather than arbitrarily hardcoding XGBoost or a single model, four candidate model families were evaluated on 50,000 synthetic records (`synthetic_development_data.csv`) using 5-fold cross-validation:

| Algorithm Candidate | Test Accuracy | F1-Score (Macro) | 5-Fold Cross-Val F1 | Selection Status |
| :--- | :---: | :---: | :---: | :---: |
| **Logistic Regression (Baseline)** | 69.16% | 0.6400 | 0.6446 &plusmn; 0.005 | Baseline Checked |
| **Random Forest Classifier** | 83.56% | 0.7924 | 0.7927 &plusmn; 0.004 | Strong Contender |
| **HistGradientBoostingClassifier** | **84.40%** | **0.8106** | **0.8065 &plusmn; 0.003** | **Selected Production** |
| **XGBoost Classifier** | 84.20% | 0.8060 | 0.8080 &plusmn; 0.003 | Production Candidate |

*Winner:* **HistGradientBoosting** achieved the highest test F1-macro (0.8106) and test accuracy (84.40%) with superior inference latency and native missing value resilience.

---

## 4. Technology Stack

- **Backend:** Python 3.11+ / Flask 3.1.3
- **ORM & Database:** Flask-SQLAlchemy 3.1.1, SQLAlchemy 2.1.1, PyMySQL (MySQL production ready, SQLite default dev)
- **Validation:** Pydantic 2.13.4 with email-validator
- **Data & ML:** scikit-learn 1.9.1, XGBoost 3.4.1, pandas 3.0.5, numpy 2.4.3, scipy 1.18.0, joblib 1.6.0
- **Security:** Werkzeug generate_password_hash / check_password_hash (scrypt/pbkdf2), HttpOnly Lax session cookies
- **Testing:** pytest 9.1.1, pytest-cov 7.1.0
- **Frontend:** Semantic HTML5, CSS3 Custom Properties (modern dark slate / emerald design system), Chart.js 4.4.1

---

## 5. Database Schema

- `users`: User identity, hashed passwords, demo flag, role (`user`, `admin`).
- `health_profiles`: Biometrics, activity level, dietary preference, goal, limitations, allergies, BMI, BMR.
- `daily_activities`: Daily steps, water, sleep hours, sleep quality, exercise minutes, type, calories, mood, anomaly flag.
- `recommendations`: Category, diet guidance JSON, exercise guidance JSON, targets, explainability string, confidence, provenance model/version, fallback level.
- `daily_tasks`: Personalized micro-goals synchronized per day with interactive completion tracking.
- `wellness_scores`: Daily 0–100 total score and 5 dimension subscores with full formula breakdown.
- `weekly_reports`: Past 7-day averages, Model C trend direction, achievements, and priority focus areas.
- `model_versions`: Historical registry tracking model artifacts, versions, metrics, algorithms, feature contracts, and rollback targets.
- `system_errors`: Diagnostic incident log capturing unique `ERROR-ID`s, category, severity, status, internal messages, and user-safe messages.
- `audit_logs`: Audit trail for logins, profile changes, model updates, and rollbacks.

---

## 6. 11-Step ML Self-Validation & Bug Diagnostics

Before any model serves user predictions, the `ModelHealthMonitor` executes 11 automated verification checks:
1. **CHECK 1:** Model file existence at artifact path.
2. **CHECK 2:** In-memory artifact loading.
3. **CHECK 3:** Preprocessing pipeline existence.
4. **CHECK 4:** Feature contract schema match (all 18 expected features present).
5. **CHECK 5:** Valid benchmark sample smoke inference.
6. **CHECK 6:** Predicted class belongs to allowed categories.
7. **CHECK 7:** Confidence probability validity (bounded in `[0.0, 1.0]`).
8. **CHECK 8:** Output classes alignment in model `classes_`.
9. **CHECK 9:** Zero NaN or infinite values in probabilities.
10. **CHECK 10:** Model version and dependency compatibility.
11. **CHECK 11:** Baseline distribution statistics availability for drift monitoring.

---

## 7. Installation & Setup

### 1. Clone & Set Up Python Environment
```bash
git clone <repo-url>
cd "AI-Powered Personalized Health Monitoring and Wellness Recommendation System"
python -m venv venv
venv\Scripts\activate   # On Windows
source venv/bin/activate # On Linux/macOS
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Initialize Environment
Copy the `.env.example` file:
```bash
cp .env.example .env
```

---

## 8. CLI Commands

### Generate 50,000+ Synthetic Records:
```bash
python scripts/generate_data.py
```

### Train & Register Production Models:
```bash
python scripts/train_models.py
```

### Validate Active Model with 11 Health Checks:
```bash
python scripts/validate_models.py
```

### Seed Database with Demo & Historical Data:
```bash
python scripts/seed_database.py
```

### Retrain Models on Fresh Data:
```bash
python scripts/retrain.py
```

### Run Full Test Suite:
```bash
pytest
```

### Launch Flask Web Application:
```bash
python app.py
```
Open **http://127.0.0.1:5000** in your browser.

---

## 9. Automated Testing & Coverage

The test suite covers:
- `test_auth.py`: Registration, password hashing, session lifecycle, invalid credentials.
- `test_profile.py`: Profile updates, deterministic BMI & Mifflin-St Jeor BMR calculations.
- `test_activity.py`: Telemetry logging, validation bounds, Model D anomaly screening.
- `test_recommendations.py`: Hybrid recommendation engine, dietary/allergy filtering, physical limitation safety filters.
- `test_wellness_score.py`: Model B calculation, weights, subscores, transparent formula strings.
- `test_ml_model.py`: ML contract testing, feature schema assertions, valid outputs, no NaNs.
- `test_model_health.py`: Full 11-step ML health auditor and data drift detector.
- `test_fallback.py`: Fault injection testing simulating missing/corrupted models and verifying Level 3/4 graceful fallback.
- `test_database.py`: Schema relations, cascades, audit and error logging.
- `test_api.py`: Full REST endpoints (`/api/health`, `/api/dashboard`, `/api/activity`, etc.).
- `test_admin.py`: Administrative dashboard, model rollback, system health.
- `test_assistant.py`: Grounded AI assistant answering and clinical safety guardrails.
- `test_progress_and_reports.py`: Chart rendering endpoints and weekly reports.

Run tests:
```bash
pytest -v
```
All **34 tests pass cleanly** in ~5 seconds.

---

## 10. Model Rollback & Retraining

If model drift or performance degradation occurs:
1. Navigate to `/admin/models` or run:
   ```bash
   python scripts/retrain.py
   ```
2. The pipeline compares the newly trained candidate against the active production model.
3. If the candidate proves superior, it is registered and the previous version is saved as the rollback target.
4. An admin can trigger an instant rollback to the previous known-good model version at any time via the `/admin/models` dashboard or the `registry.rollback()` API.

---

## 11. Demo Accounts & Viva Presentation

For viva, demonstration, or evaluation, pre-seeded accounts are provided:

| Account Type | Email | Password | Role | Features |
| :--- | :--- | :--- | :--- | :--- |
| **Demo User** | `demo@wellness.ai` | `DemoPass123!` | Standard User | 30 days of rich activity history, weekly reports, daily tasks, wellness scores |
| **Administrator** | `admin@wellness.ai` | `AdminPass123!` | Admin | Model registry, 11-step ML health audit, drift monitor, error diagnostics |

*Quick Fill:* The `/login` page includes **"Demo User"** and **"Admin ML"** quick-fill buttons for instant 1-click access.

---

## 12. Privacy & Security

- **Password Security:** Passwords hashed using industry-standard Werkzeug scrypt/pbkdf2 hashing.
- **Session Protection:** Session cookies enforced with `HttpOnly` and `SameSite=Lax`.
- **SQL Injection Prevention:** 100% parameterized queries via SQLAlchemy ORM.
- **Centralized Error Shielding:** Normal users receive friendly, actionable messages while diagnostic details and stack traces are logged with unique `ERROR-ID`s visible only to administrators.
- **No Clinical Diagnostics:** Strict safety layer screening queries containing acute symptoms and directing users to qualified healthcare professionals.
