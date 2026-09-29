# Vendor Agnostic Compliance Engine

## Overview
The **Vendor Agnostic Compliance Engine** is a full-stack application designed to automatically parse, normalize, and assess network device configurations against industry-standard compliance frameworks (such as CIS, NIST 800-53, and STIG).

It allows organizations to upload raw configurations from various network devices (like Cisco IOS, Juniper, etc.) and evaluates them without relying on proprietary or vendor-specific agents. The system intelligently detects the device type, extracts key parameters, checks them against predefined compliance rules, and generates actionable findings and reports.

## How It Works (In-Depth)
The application architecture is divided into two main components: a **FastAPI backend** and a **React/Vite frontend**.

### 1. Ingestion & Detection
* **Raw Config Upload:** Users upload the raw configuration files of their devices.
* **Fingerprinting:** The backend engine uses YAML-based fingerprint packs (located in `backend/app/parsers/packs`) to heuristically detect the vendor, operating system, and OS version of the uploaded configuration.
* **Confidence Scoring:** It calculates a confidence score for the detection and falls back to manual or LLM-assisted categorization if the score is below a certain threshold.

### 2. Parsing & Normalization
* **Data Extraction:** Once the device type is detected, the engine runs parsing specifications to extract vital fields (like hostname, firmware version, interfaces, and specific security settings).
* **Normalization:** Extracted data is normalized into a standard format (`NormalizedField`) regardless of the original vendor syntax, allowing unified compliance checks.

### 3. Compliance Assessment
* **Framework Rules:** The system uses YAML-based rule packs (e.g., `cis_ios.yaml`, `nist_800_53.yaml`, `stig_generic.yaml` located in `backend/app/rules/packs`) to define compliance expectations.
* **Findings Generation:** The normalized fields are evaluated against these rules. If a configuration parameter fails to meet the rule's criteria, a "Finding" is generated.

### 4. Reporting
* **PDF & Data Export:** The backend utilizes tools like WeasyPrint and ReportLab to generate comprehensive, downloadable compliance reports outlining the device's status, passed checks, and remediation steps for failed checks.

---

## Architecture Stack

### Backend
* **Framework:** FastAPI
* **ORM:** SQLModel
* **Database:** SQLite (default) / PostgreSQL (via psycopg2)
* **Report Generation:** WeasyPrint, ReportLab, Jinja2
* **Language:** Python 3.10+

### Frontend
* **Framework:** React 19
* **Build Tool:** Vite
* **Language:** TypeScript
* **Styling:** Tailwind CSS (PostCSS)
* **Linting:** Oxlint

---

## Setup Instructions

Follow these steps to set up the project locally for development.

### Prerequisites
* **Python 3.10+**
* **Node.js 18+** (and npm/yarn)

### 1. Backend Setup

1. **Navigate to the backend directory:**
   ```bash
   cd backend
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   ```

3. **Activate the virtual environment:**
   * **Windows:** `venv\Scripts\activate`
   * **macOS/Linux:** `source venv/bin/activate`

4. **Install the dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

5. **Run the backend server:**
   ```bash
   uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
   ```
   *The API will be accessible at `http://127.0.0.1:8000`. You can view the Swagger UI docs at `http://127.0.0.1:8000/docs`.*

### 2. Frontend Setup

1. **Open a new terminal and navigate to the frontend directory:**
   ```bash
   cd frontend
   ```

2. **Install the dependencies:**
   ```bash
   npm install
   ```

3. **Run the development server:**
   ```bash
   npm run dev
   ```
   *The frontend application will start, and the terminal will display the local URL (usually `http://localhost:5173`).*

## Docker (Optional)
Both the frontend and backend include `Dockerfile`s, meaning the application can be containerized and run using Docker or Docker Compose if desired.
