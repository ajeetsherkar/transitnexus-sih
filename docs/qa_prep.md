# TransitNexus — Round 2 Judge Q&A Prep

## 1. One-Line Project Explanation

> TransitNexus is an AI-powered urban mobility intelligence platform that converts traffic video into structured mobility events, aggregates those events into zone-level intelligence, and exposes the results through APIs and dashboards.

## 2. Real vs Simulated vs Production

| Component | Current Prototype | Production Plan |
|---|---|---|
| Video feed | Processed sample traffic/fleet video clips | Live bus-mounted camera feeds |
| GPS | Simulated route/location data | Real GPS telemetry from buses |
| OCR / Plate | Mock OCR / plate fallback | Production-grade ALPR/OCR pipeline |
| Congestion / Delay Models | Prototype-trained models using demonstration data | Retrain and validate using real-world traffic and fleet ground-truth data |
| Event Storage | Structured JSON event storage | Production database / persistent event store |

### Rehearsed Answer

> We validated the full event-to-intelligence pipeline using processed video and simulated fleet/location data. The production version connects the same event schema and intelligence pipeline to real bus-mounted camera and GPS feeds.

## 3. Can You Test a New Video?

> Yes. The inference pipeline accepts a video source dynamically. A new traffic video can be passed to the YOLO inference pipeline, converted into the same structured event schema, and then consumed by the existing API and dashboard layers.

### Important Limitation

> The current prototype validates video-file ingestion. It is not yet a complete live RTSP camera-ingestion system.

## 4. Can You Handle a Live Bus Camera?

> The current prototype uses video-file ingestion. For production, the video source can be replaced by a live bus-mounted camera or RTSP stream while keeping the downstream event schema, intelligence layer, APIs, and dashboard architecture the same.

## 5. Is the GPS Real?

> GPS coordinates in the prototype are simulated along the demonstration route. Production deployment would consume real GPS telemetry from the buses.

## 6. How Does the Pipeline Work?

> Traffic video is processed with YOLOv8. Detected objects are converted into structured urban mobility events containing event type, confidence, GPS, timestamp, and frame path. Events are stored and served through FastAPI, while aggregation and ML layers generate zone-level intelligence and predictions.

## 7. What Machine Learning Models Are Used?

> We use Random Forest for congestion-severity classification and Gradient Boosting for route-delay regression. The models use engineered zone and time-window features generated from the processed event stream.

## 8. What Are Your ML Metrics?

> On the prototype data, Random Forest achieved 75% accuracy with a weighted F1 of 0.75, while Gradient Boosting achieved an RMSE of 6.7333 minutes.

### Critical Caveat

> These are prototype evaluation metrics, not claims of real-world traffic prediction accuracy. The congestion labels are derived from density-score quantiles, and the route-delay target is simulated from observed event density/counts.

## 9. Why Are Your ML Results Not Real-World Accuracy?

> The prototype does not yet have sufficient real-world ground-truth traffic and fleet data. We therefore use the available demonstration data to validate that the ML pipeline works end-to-end. Production models would be retrained and validated against real-world ground truth.

## 10. What Happens If You Get Duplicate Detections?

> In a production system, temporal and spatial deduplication would be applied using object identity, timestamps, location proximity, and tracking information before events are persisted as independent incidents.

## 11. Do You Have Object Tracking?

> The current prototype focuses on detection and event generation rather than a production-grade multi-object tracking layer. Tracking would be added using persistent object IDs across frames to distinguish a continuously observed vehicle from a new vehicle.

## 12. How Would You Prevent Double Counting?

> We would combine tracking IDs with temporal and spatial rules. A vehicle detected across consecutive frames would remain one tracked object, while a new object entering the scene would receive a new identity. Event-level deduplication would additionally use time, location, event type, and confidence.

## 13. How Would You Scale This to Hundreds or Thousands of Buses?

> The inference and API layers can be separated into independently scalable services. Video processing can be distributed across workers, events can be placed in a persistent event store or message queue, and API/dashboard services can scale horizontally. Kubernetes can orchestrate replicas, health checks, and resource allocation.

## 14. Why Kubernetes?

> Kubernetes provides a production orchestration layer for independently scaling inference, API, and supporting services. It can manage replicas, service discovery, health checks, rolling deployments, and resource limits.

### Prototype Limitation

> Kubernetes is part of the production architecture direction; the current demo is focused on validating the end-to-end intelligence pipeline rather than operating a large production fleet.

## 15. How Would Authentication Work?

> Production APIs would use authenticated access, such as JWT or an API gateway, with role-based permissions for operators, administrators, and fleet services. The current prototype focuses on functionality and does not implement production authentication.

## 16. How Would You Store Events in Production?

> The prototype uses structured JSON event storage. Production would use a persistent database or event store so events can be indexed by bus, route, timestamp, location, and event type.

## 17. Why JSON Instead of a Database?

> JSON keeps the prototype simple and reproducible while validating the complete pipeline. At production scale, a persistent database or event store would provide indexing, concurrency, retention, and scalable querying.

## 18. What Is the ONNX Result?

> We benchmarked PyTorch and ONNX Runtime on the same 50 decoded frames on an Apple M2 CPU. ONNX Runtime was slower in this particular test: 13.43% slower for the vehicle model and 71.43% slower for the pothole model.

### Important Answer

> We do not claim that ONNX is automatically faster. The benchmark establishes a portable inference representation that can be evaluated and optimized for the eventual edge hardware and execution provider.

## 19. Why Use ONNX If It Is Slower?

> ONNX provides a portable inference representation and allows us to evaluate different runtime and hardware configurations. The current M2 CPU benchmark does not show a speed advantage, so production deployment would benchmark the exported models on the actual target edge hardware and execution provider.

## 20. What If the Judge Gives You a New Video?

> We can pass the new video as the inference source, run the detection pipeline, generate the standardized events, and feed those events into the existing API and dashboard. The current prototype is designed around video-file ingestion; live camera ingestion is the production extension.

## 21. What Is Actually Live in the Demo?

> The dashboard connects to the FastAPI backend, and the system supports live alert delivery through WebSocket communication. The underlying demonstration event dataset is generated from processed video rather than a live bus camera feed.

## 22. What Is the Main Production Gap?

> The main gaps are real bus camera and GPS ingestion, production-grade tracking and deduplication, real-world ground-truth data for model training, persistent event storage, authentication, and production-scale orchestration.

## 23. Why Should We Trust the Prototype?

> We focus on transparency: the prototype clearly separates validated components from simulated inputs and future production components. We have verified the inference pipeline, event schema, APIs, ML pipeline, dashboards, and live alert path without presenting simulated data as real-world accuracy.

# Team Rehearsal — Roles

### Demo Owner

Responsible for:
- Starting the demo
- Showing the dashboard
- Map and event markers
- Fleet Status
- Zone Summary
- Recent Alerts
- AI Predictions
- Triggering / explaining live WebSocket alert
- Showing Event Details

### Technical / ML Owner

Responsible for:
- YOLO detection
- Event schema
- ML models
- Features
- Metrics
- ML limitations
- New video testing
- Tracking and deduplication
- ONNX benchmark

### Architecture / Scalability Owner

Responsible for:
- End-to-end architecture
- FastAPI
- WebSocket
- Production data flow
- Authentication
- Database migration
- Kubernetes
- Scaling to many buses
- Live camera/GPS architecture

### All Team Members

Every member should know these five answers:
1. What does TransitNexus do?
2. What is real vs simulated?
3. What happens if a new video is provided?
4. What are the biggest production limitations?
5. Why is the project technically scalable?

# Final Judge Mindset

> Do not claim prototype functionality as production functionality.

> Clearly distinguish what is implemented, what is simulated, and what would be changed for production.

> Prefer a technically honest answer over an exaggerated claim.
