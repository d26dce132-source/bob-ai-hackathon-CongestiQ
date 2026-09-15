# Architecture

## System Architecture
# CongestiQ Architecture

CongestiQ uses a React frontend connected to a Python FastAPI backend. The backend manages vessel schedules and port resources, performs congestion and risk analysis, runs berth and crane optimization, generates routing recommendations, and produces a prioritized 72-hour operations plan.

```mermaid

## Architecture Diagram

```mermaid
flowchart TD
    A["Vessel Schedules + Port Resources"]
    B["CongestiQ Backend<br/>Python + FastAPI"]

    A --> B

    B --> C["Congestion Prediction"]
    B --> D["Vessel Risk Detection"]
    B --> E["Congestion Hotspot Detection"]

    C --> F["Berth Assignment Optimization"]
    D --> F
    E --> F

    F --> G["Crane Assignment Optimization"]
    G --> H["Alternative Routing Recommendations"]

    H --> I["72-Hour Operations Plan"]

    I --> J["REST API"]

    J --> K["React Dashboard"]

    K --> L["Port Operator"]
```

## Components

| Component | Technology | Responsibility |
|---|---|---|
| Frontend | React + Vite | Dashboard UI, visualization, and user interaction |
| Backend API | Python + FastAPI | Business logic, orchestration, and REST API endpoints |
| Congestion Prediction | Python | Predicting port-wide congestion across the 72-hour planning horizon |
| Vessel Risk Detection | Python | Calculating vessel congestion-risk scores and risk levels |
| Hotspot Detection | Python | Identifying and scoring congestion hotspots |
| Berth Optimization | Python | Evaluating and recommending berth assignments |
| Crane Optimization | Python | Evaluating crane requirements and recommending available cranes |
| Routing Recommendations | Python | Generating alternative operational routing actions |
| 72-Hour Operations Plan | Python | Generating prioritized operational actions |
| Database | SQLite / PostgreSQL | Storing vessel, berth, crane, and schedule data |
| API Documentation | OpenAPI / Swagger | Providing interactive API documentation |
| Development Environment | IBM Bob | AI-powered development, coding, testing, and project workflow |

## Data Flow

1. Vessel schedules and port resource data are loaded into the backend.
2. The FastAPI backend retrieves operational data from the database.
3. Congestion prediction analyzes vessel schedules and available port capacity.
4. Vessel risk detection calculates congestion-risk scores for vessels.
5. Hotspot detection identifies areas with high congestion pressure.
6. Berth optimization evaluates vessel schedules and recommends berth assignments.
7. Crane optimization evaluates vessel requirements and recommends suitable cranes.
8. Routing analysis generates alternative operational recommendations for significant-risk vessels.
9. The system combines these results into a prioritized 72-hour operations plan.
10. REST API endpoints expose the results to the React frontend.
11. The React dashboard displays the results to the port operator.

## Security Considerations

Environment-specific configuration is stored in .env.
.env files containing local configuration are not intended to be committed to the repository.
.env.example provides configuration guidance without real secrets.
No real API keys or credentials are required by the current local prototype.
Real production deployment should use secure secret management and authenticated API access.
[Note any security decisions relevant to the architecture — even if basic.]


## Scalability Notes

The current implementation is a hackathon prototype using simulated operational data.

For production deployment, the architecture could be extended with:

Live AIS and vessel schedule feeds
Real-time berth and crane availability
Historical operational datasets
PostgreSQL as the primary production database
Horizontally scalable FastAPI services
Background processing for large prediction and optimization workloads
Authentication and role-based access control
Real-time alerts and operational integrations
Multi-port optimization and routing

## Prototype Scope

The current prototype demonstrates the complete port decision-support workflow using simulated operational data.

CongestiQ's predictions and recommendations are intended for demonstration and planning purposes. A production system would require integration with live vessel, berth, crane, and port-management data.